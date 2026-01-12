"""
S级交易员仓位监控脚本

功能说明：
1. 获取所有S级的交易员
2. 更新交易员的当前仓位并保存到数据库（通过获取交易记录实现更新开仓时间）
3. 如果发现有新仓位，通过飞书通知

运行模式：
- 定时循环执行：每隔N分钟运行一次
- 一次性执行：运行一次后退出（使用 --once 参数）
"""
import sys
import time
import argparse
from pathlib import Path
from typing import List, Dict, Set, Optional
from datetime import datetime

from loguru import logger

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from hyperliquid.info import Info
from hyperliquid.utils import constants

from database import TraderDatabase
from screener.api_client import SyncAPIClient, APIConfig
from clients.feishu_client import FeishuClient
from config.settings import settings


def get_s_rated_traders(db: TraderDatabase) -> List[Dict]:
    """
    获取所有S级交易员
    
    Args:
        db: 数据库实例
    
    Returns:
        S级交易员列表
    """
    traders = db.get_traders_by_rating('S')
    logger.info(f"获取到 {len(traders)} 个S级交易员")
    return traders


def get_current_positions_from_db(db: TraderDatabase, address: str) -> Dict[str, Dict]:
    """
    从数据库获取交易员的当前持仓
    
    Args:
        db: 数据库实例
        address: 交易员地址
    
    Returns:
        {coin: position_data} 字典
    """
    positions = db.get_positions(address)
    return {pos['coin']: pos for pos in positions}


def fetch_latest_fills(client: SyncAPIClient, address: str) -> List[Dict]:
    """
    从API获取交易员最近的交易记录
    
    Args:
        client: API客户端
        address: 交易员地址
    
    Returns:
        交易记录列表
    """
    try:
        fills = client.get_user_fills(address, limit=0)  # 获取最近2000条
        return fills if fills else []
    except Exception as e:
        logger.error(f"获取交易记录失败 {address[:10]}...: {e}")
        return []


def fetch_latest_positions(info: Info, address: str) -> List[Dict]:
    """
    从API获取交易员最新的持仓
    
    Args:
        info: Hyperliquid Info 实例
        address: 交易员地址
    
    Returns:
        持仓列表 (assetPositions)
    """
    try:
        user_state = info.user_state(address)
        if not user_state:
            return []
        return user_state.get('assetPositions', [])
    except Exception as e:
        logger.error(f"获取持仓失败 {address[:10]}...: {e}")
        return []


def detect_new_positions(
    old_positions: Dict[str, Dict],
    new_positions: Dict[str, Dict]
) -> List[Dict]:
    """
    检测新开的仓位
    
    Args:
        old_positions: 更新前的持仓 {coin: position_data}
        new_positions: 更新后的持仓 {coin: position_data}
    
    Returns:
        新仓位列表
    """
    old_coins = set(old_positions.keys())
    new_coins = set(new_positions.keys())
    
    # 新出现的币种就是新仓位
    new_coin_set = new_coins - old_coins
    
    new_positions_list = []
    for coin in new_coin_set:
        pos = new_positions[coin]
        new_positions_list.append(pos)
    
    return new_positions_list


def format_position_direction(szi: float) -> tuple[str, str]:
    """
    根据szi判断仓位方向
    
    Args:
        szi: 仓位数量（正数=多，负数=空）
    
    Returns:
        (方向文字, emoji)
    """
    if szi > 0:
        return "做多", "🟢"
    else:
        return "做空", "🔴"


def send_new_position_notification(
    feishu: FeishuClient,
    address: str,
    position: Dict,
    trader_name: str = None
) -> bool:
    """
    发送新仓位通知
    
    Args:
        feishu: 飞书客户端
        address: 交易员地址
        position: 仓位数据
        trader_name: 交易员名称（可选）
    
    Returns:
        是否发送成功
    """
    coin = position.get('coin', 'Unknown')
    szi = float(position.get('szi', 0))
    entry_px = float(position.get('entry_px', 0))
    position_value = abs(float(position.get('position_value', 0)))
    leverage_value = int(position.get('leverage_value', 1))
    open_time = position.get('open_time', '')
    
    direction, emoji = format_position_direction(szi)
    
    # 格式化开仓时间
    open_time_str = "未知"
    if open_time:
        try:
            # 尝试解析ISO格式时间
            if isinstance(open_time, str):
                open_time_str = open_time[:19].replace('T', ' ')
        except:
            open_time_str = str(open_time)
    
    # 构建通知内容
    trader_display = trader_name if trader_name else f"{address[:10]}..."
    
    content = f"""**交易员**: `{trader_display}`
**地址**: `{address[:16]}...`
**币种**: {coin}
**方向**: {emoji} {direction}
**数量**: {abs(szi):.4f}
**入场价**: ${entry_px:,.4f}
**仓位价值**: ${position_value:,.2f}
**杠杆**: {leverage_value}x
**开仓时间**: {open_time_str}"""

    title = f"🆕 新仓位 - {coin} {direction}"
    color = "green" if szi > 0 else "red"
    
    return feishu.send_card(title=title, content=content, color=color)


def process_trader(
    db: TraderDatabase,
    api_client: SyncAPIClient,
    info: Info,
    feishu: FeishuClient,
    trader: Dict,
    dry_run: bool = False
) -> int:
    """
    处理单个交易员：更新数据并检测新仓位
    
    Args:
        db: 数据库实例
        api_client: API客户端
        info: Hyperliquid Info实例
        feishu: 飞书客户端
        trader: 交易员信息
        dry_run: 是否仅预览不发送通知
    
    Returns:
        新仓位数量
    """
    address = trader['address']
    trader_name = trader.get('trader_name')  # 可能有别名
    
    logger.info(f"处理交易员: {address[:16]}...")
    
    # 1. 获取数据库中的当前持仓（用于对比）
    old_positions = get_current_positions_from_db(db, address)
    old_coins = set(old_positions.keys())
    logger.debug(f"  数据库中持仓: {len(old_positions)} 个 - {list(old_coins)}")
    
    # 2. 获取最新的交易记录并保存
    fills = fetch_latest_fills(api_client, address)
    if fills:
        saved_count = db.save_fills(address, fills)
        logger.info(f"  保存交易记录: {saved_count} 条")
    else:
        logger.debug(f"  无新交易记录")
    
    # 3. 获取最新持仓
    asset_positions = fetch_latest_positions(info, address)
    
    if not asset_positions:
        logger.info(f"  当前无持仓")
        # 清空数据库中的持仓
        db.save_positions(address, [])
        return 0
    
    # 4. 保存持仓到数据库（会自动获取开仓时间）
    positions_saved = db.save_positions(address, asset_positions)
    logger.info(f"  保存持仓: {positions_saved} 个")
    
    # 5. 获取更新后的持仓（包含开仓时间）
    new_positions = get_current_positions_from_db(db, address)
    new_coins = set(new_positions.keys())
    logger.debug(f"  更新后持仓: {len(new_positions)} 个 - {list(new_coins)}")
    
    # 6. 检测新仓位
    new_position_list = detect_new_positions(old_positions, new_positions)
    
    if not new_position_list:
        logger.info(f"  无新仓位")
        return 0
    
    logger.success(f"  检测到 {len(new_position_list)} 个新仓位!")
    
    # 7. 发送通知
    for pos in new_position_list:
        coin = pos.get('coin', 'Unknown')
        szi = float(pos.get('szi', 0))
        direction, _ = format_position_direction(szi)
        
        if dry_run:
            logger.info(f"    [DRY-RUN] 新仓位: {coin} {direction} {abs(szi):.4f}")
        else:
            success = send_new_position_notification(
                feishu, address, pos, trader_name
            )
            if success:
                logger.success(f"    ✓ 已通知: {coin} {direction}")
            else:
                logger.error(f"    ✗ 通知失败: {coin}")
    
    return len(new_position_list)


def run_monitoring_cycle(
    db: TraderDatabase,
    api_client: SyncAPIClient,
    info: Info,
    feishu: FeishuClient,
    dry_run: bool = False
) -> Dict:
    """
    运行一次监控周期
    
    Args:
        db: 数据库实例
        api_client: API客户端
        info: Hyperliquid Info实例
        feishu: 飞书客户端
        dry_run: 是否仅预览
    
    Returns:
        统计信息
    """
    stats = {
        'traders_processed': 0,
        'new_positions_total': 0,
        'errors': 0
    }
    
    # 获取S级交易员
    traders = get_s_rated_traders(db)
    
    if not traders:
        logger.warning("没有找到S级交易员")
        return stats
    
    logger.info(f"开始处理 {len(traders)} 个S级交易员")
    logger.info("-" * 60)
    
    for i, trader in enumerate(traders, 1):
        try:
            logger.info(f"[{i}/{len(traders)}]", end=" ")
            new_count = process_trader(
                db, api_client, info, feishu, trader, dry_run
            )
            stats['traders_processed'] += 1
            stats['new_positions_total'] += new_count
            
        except Exception as e:
            logger.error(f"处理交易员失败 {trader['address'][:10]}...: {e}")
            stats['errors'] += 1
        
        # API 调用间隔
        if i < len(traders):
            time.sleep(1.0)
    
    logger.info("-" * 60)
    logger.info(f"本轮完成: 处理 {stats['traders_processed']} 个交易员, "
                f"发现 {stats['new_positions_total']} 个新仓位, "
                f"错误 {stats['errors']} 个")
    
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="S级交易员仓位监控脚本"
    )
    parser.add_argument(
        "--interval", "-i",
        type=int,
        default=5,
        help="循环间隔（分钟），默认: 5"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="仅运行一次后退出"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="仅预览，不发送通知"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("S级交易员仓位监控脚本")
    logger.info("=" * 60)
    logger.info(f"运行模式: {'一次性执行' if args.once else f'循环执行（间隔 {args.interval} 分钟）'}")
    if args.dry_run:
        logger.info("预览模式: 不发送飞书通知")
    logger.info("")
    
    # 初始化数据库
    logger.info("初始化数据库连接...")
    db = TraderDatabase()
    logger.success("✓ 数据库连接成功")
    
    # 初始化 API 客户端
    logger.info("初始化 API 客户端...")
    config = APIConfig()
    config.api_call_delay = 0.5
    config.max_retries = 3
    
    try:
        api_client = SyncAPIClient(config)
        logger.success("✓ API 客户端初始化成功")
    except Exception as e:
        logger.error(f"API 客户端初始化失败: {e}")
        db.close()
        return
    
    # 初始化 Hyperliquid Info
    logger.info("初始化 Hyperliquid Info...")
    info = Info(constants.MAINNET_API_URL, skip_ws=True)
    logger.success("✓ Hyperliquid Info 初始化成功")
    
    # 初始化飞书客户端
    logger.info("初始化飞书客户端...")
    feishu = FeishuClient(
        app_id=settings.feishu.app_id,
        app_secret=settings.feishu.app_secret,
        webhook_url=settings.feishu.webhook_url,
        default_user_id=settings.feishu.default_user_id
    )
    
    if not feishu.webhook_url and not feishu.app_id:
        logger.warning("⚠ 飞书未配置，通知功能将不可用")
    else:
        logger.success("✓ 飞书客户端初始化成功")
    
    logger.info("")
    
    # 主循环
    cycle_count = 0
    try:
        while True:
            cycle_count += 1
            logger.info(f"{'='*60}")
            logger.info(f"第 {cycle_count} 轮监控 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"{'='*60}")
            
            run_monitoring_cycle(db, api_client, info, feishu, args.dry_run)
            
            if args.once:
                logger.info("一次性执行完成，退出")
                break
            
            logger.info(f"等待 {args.interval} 分钟后进行下一轮...")
            time.sleep(args.interval * 60)
            
    except KeyboardInterrupt:
        logger.warning("\n用户中断")
    finally:
        db.close()
        logger.info("数据库连接已关闭")


if __name__ == "__main__":
    main()
