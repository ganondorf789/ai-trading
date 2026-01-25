"""
仓位级别跟单机器人

第二种跟单模式：跟单特定交易员的特定仓位
通过轮询目标交易者的特定仓位变化进行跟单
从数据库加载仓位跟单配置，支持同时跟单多个仓位
使用前请先在 Web 持仓页面点击"跟单此仓位"按钮添加跟单

支持两种添加跟单方式：
1. Web 持仓页面点击"跟单此仓位"按钮
2. 飞书消息卡片点击"跟单此仓位"按钮（需启动回调服务）

启动方式：
- 仅跟单机器人: python examples/position_copy_trading_example.py
- 仅飞书回调: python examples/position_copy_trading_example.py callback
- 两者同时: python examples/position_copy_trading_example.py all
"""

VERSION = "1.0.0"
import asyncio
import os
import sys
import threading
import pendulum

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loguru import logger
from clients.hyperliquid_client import HyperliquidClient
from clients.feishu_client import (
    FeishuClient, CopyTradingNotifier, FeishuCallbackClient, CardActionEvent,
    build_success_card, build_warning_card, build_error_card, build_info_card, build_card_with_buttons
)
from engine.position_copy_trading import (
    PositionCopyTradingBot, 
    REDIS_OPEN_CHANNEL, REDIS_ADJUST_CHANNEL, REDIS_CLOSE_CHANNEL,
    REDIS_MY_POSITIONS_KEY, REDIS_MY_BALANCE_KEY
)
from config.settings import settings
from database import TraderDatabase

# Redis 支持（可选）
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# 全局通知器
notifier: CopyTradingNotifier = None
# 全局数据库
db: TraderDatabase = None
# 全局 Redis 客户端（用于发送开仓通知）
redis_client = None
# 全局 Hyperliquid 客户端（复用实例，避免重复创建）
hl_client: HyperliquidClient = None
# 全局飞书客户端（用于回调处理，复用实例）
feishu_position_client: FeishuClient = None


def setup_logging():
    """配置日志"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
        level="INFO"
    )
    logger.add(
        f"logs/position_copy_{pendulum.now().format('YYYYMMDD_HHmmss')}.log",
        rotation="1 day",
        level="DEBUG"
    )


def setup_feishu_notifier() -> CopyTradingNotifier:
    """初始化飞书通知器"""
    feishu_client = FeishuClient(
        app_id=settings.feishu.app_id,
        app_secret=settings.feishu.app_secret,
        default_user_id=settings.feishu.default_user_id
    )

    # 检查是否配置了飞书
    if settings.feishu.app_id and settings.feishu.app_secret:
        logger.info("飞书应用已配置")
    else:
        logger.warning("飞书未配置，将不会发送通知")

    return CopyTradingNotifier(feishu_client)


def setup_redis_client():
    """初始化 Redis 客户端（用于发送配置重载通知）"""
    global redis_client
    
    if not REDIS_AVAILABLE:
        logger.warning("Redis 库未安装，配置重载通知将不可用")
        return None
    
    try:
        redis_client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            password=settings.redis.password or None,
            db=settings.redis.db,
            decode_responses=True
        )
        redis_client.ping()
        logger.info(f"Redis 已连接，开仓通知已启用")
        return redis_client
    except Exception as e:
        logger.warning(f"Redis 连接失败: {e}")
        redis_client = None
        return None


def notify_open_position(tracking_id: int):
    """发送开仓通知到 Redis，机器人收到后立即开仓"""
    global redis_client
    
    if redis_client is None:
        return False
    
    try:
        redis_client.publish(REDIS_OPEN_CHANNEL, str(tracking_id))
        logger.info(f"已发送开仓通知: tracking_id={tracking_id}")
        return True
    except Exception as e:
        logger.warning(f"发送开仓通知失败: {e}")
        return False


def get_cached_positions():
    """
    从 Redis 缓存获取当前仓位（由跟单机器人定期更新）
    
    Returns:
        (positions_list, available_balance) 或 (None, None) 如果缓存不存在
    """
    global redis_client
    
    if redis_client is None:
        return None, None
    
    try:
        import json
        
        # 读取仓位
        positions_json = redis_client.get(REDIS_MY_POSITIONS_KEY)
        balance_str = redis_client.get(REDIS_MY_BALANCE_KEY)
        
        if positions_json is None:
            return None, None
        
        positions = json.loads(positions_json)
        balance = float(balance_str) if balance_str else 0.0
        
        return positions, balance
    except Exception as e:
        logger.debug(f"从 Redis 读取仓位缓存失败: {e}")
        return None, None


def on_copy_callback(tracking_id: int, target: str, symbol: str, side: str, size: float):
    """复制交易回调"""
    logger.success(f"[#{tracking_id}] 开仓成功: {symbol} {side.upper()} {size} (目标: {target[:8]}...)")

    # 发送飞书通知
    if notifier:
        try:
            notifier.notify_copy_open(
                target_address=target,
                symbol=symbol,
                side=side,
                size=size
            )
        except Exception as e:
            logger.warning(f"飞书通知失败: {e}")


def on_close_callback(tracking_id: int, target: str, symbol: str, pnl: float):
    """平仓回调"""
    emoji = "+" if pnl >= 0 else ""
    logger.info(f"[#{tracking_id}] 平仓: {symbol} PnL: ${emoji}{pnl:.2f} (目标: {target[:8]}...)")

    # 发送飞书通知
    if notifier:
        try:
            notifier.notify_copy_close(
                target_address=target,
                symbol=symbol,
                pnl=pnl
            )
        except Exception as e:
            logger.warning(f"飞书通知失败: {e}")


def on_error_callback(error: Exception):
    """错误回调"""
    logger.error(f"错误: {error}")

    # 发送飞书通知
    if notifier:
        try:
            notifier.notify_error(str(error))
        except Exception as e:
            logger.warning(f"飞书通知失败: {e}")


def on_adjust_callback(tracking_id: int, target: str, symbol: str, side: str, size: float, is_increase: bool):
    """调整仓位回调（加仓/减仓）"""
    action = "加仓" if is_increase else "减仓"
    logger.info(f"[#{tracking_id}] {action}: {symbol} {side.upper()} {size} (目标: {target[:8]}...)")

    # 发送飞书通知
    if notifier:
        try:
            notifier.notify_copy_adjust(
                target_address=target,
                symbol=symbol,
                side=side,
                size=size,
                is_increase=is_increase
            )
        except Exception as e:
            logger.warning(f"飞书通知失败: {e}")


# ==================== 飞书回调处理 ====================

def handle_quick_position_tracking(event: CardActionEvent):
    """
    处理一键跟单仓位按钮点击
    
    从飞书卡片接收交易员地址和币种，添加到仓位跟单列表
    """
    global db
    
    address = event.action_value.get("address", "")
    coin = event.action_value.get("coin", "")
    trader_name = event.action_value.get("trader_name", "")
    ratio = event.action_value.get("ratio")  # 按钮传递的跟单比例（百分比，如 10, 20, 30）
    
    if not address:
        return _build_error_card("地址信息缺失")
    
    if not coin:
        return _build_error_card("币种信息缺失")
    
    logger.info(f"[仓位跟单回调] 用户 {event.user_id} 请求跟单:")
    logger.info(f"  - 交易员地址: {address}")
    logger.info(f"  - 币种: {coin}")
    logger.info(f"  - 名称: {trader_name}")
    logger.info(f"  - 按钮比例: {ratio}%") if ratio else None
    
    try:
        # 确保数据库已初始化
        if db is None:
            db = TraderDatabase()
        
        # 检查是否已存在活跃的跟单
        if db.check_position_tracking_exists(address, coin):
            return _build_warning_card(
                f"已存在 {coin} 的活跃跟单",
                f"地址: {address[:16]}..."
            )
        
        # 获取默认跟单配置
        default_config = db.get_default_copy_config()
        
        # 计算跟单比例：优先使用按钮传递的 ratio，否则使用默认配置
        if ratio is not None:
            copy_ratio = float(ratio) / 100.0  # 按钮传的是百分比，转换为小数
        else:
            copy_ratio = default_config.get('copy_ratio', 0.1)
        
        # 构建跟单数据
        tracking_data = {
            'target_address': address,
            'target_name': trader_name or "",
            'symbol': coin,
            'is_enabled': True,
            'copy_ratio': copy_ratio,
            'max_position_size_usd': default_config.get('max_position_size_usd', 500),
            'min_position_size_usd': default_config.get('min_position_size_usd', 20),
            'copy_leverage': default_config.get('copy_leverage', True),
            'max_leverage': default_config.get('max_leverage', 10),
            'default_leverage': default_config.get('default_leverage', 5),
            'slippage': default_config.get('slippage', 0.01),
            'status': 'pending',
        }
        
        # 保存到数据库
        tracking_id = db.save_position_tracking(tracking_data)
        
        if tracking_id:
            trader_display = trader_name if trader_name else f"{address[:10]}..."
            
            logger.success(f"[仓位跟单回调] 添加成功: #{tracking_id} {coin} @ {trader_display} (比例: {copy_ratio * 100:.0f}%)")
            
            # 发送 Redis 开仓通知，让机器人立即开仓
            notify_open_position(tracking_id)
            
            return _build_success_card(
                f"已添加 {coin} 仓位跟单",
                f"**目标**: {trader_display}\n**地址**: `{address[:16]}...`\n**跟单比例**: {copy_ratio * 100:.0f}%\n**状态**: 正在开仓..."
            )
        else:
            return _build_error_card("保存跟单配置失败")
            
    except Exception as e:
        logger.error(f"[仓位跟单回调] 错误: {e}")
        return _build_error_card(f"操作失败: {str(e)}")


def handle_current_position(event: CardActionEvent):
    """
    处理"当前仓位"菜单点击
    
    优先从 Redis 缓存获取仓位（由跟单机器人定期更新），响应更快
    """
    global feishu_position_client
    
    logger.info(f"[当前仓位] 用户 {event.user_id} 查询当前仓位")
    
    # 使用全局飞书客户端
    feishu_client = feishu_position_client
    
    try:
        # 从 Redis 缓存获取仓位和余额（由跟单机器人定期更新）
        positions, available_balance = get_cached_positions()
        
        if positions is None:
            card = build_warning_card(
                "缓存不可用",
                "仓位缓存不存在，请确保跟单机器人正在运行"
            )
            _send_card_to_user(feishu_client, event.user_id, card)
            return None
        
        logger.debug(f"[当前仓位] 使用 Redis 缓存，仓位数: {len(positions)}")
        
        if not positions:
            card = build_info_card(
                "📊 当前仓位",
                "暂无持仓"
            )
            _send_card_to_user(feishu_client, event.user_id, card)
            return None
        
        # 构建卡片元素
        elements = []
        total_unrealized_pnl = 0.0
        total_position_value = 0.0
        
        for pos in positions:
            # 从字典获取数据
            symbol = pos.get('symbol', '')
            side = pos.get('side', 'long')
            size = pos.get('size', 0)
            entry_price = pos.get('entry_price', 0)
            current_price = pos.get('current_price', 0)
            leverage = pos.get('leverage', 1)
            unrealized_pnl = pos.get('unrealized_pnl', 0)
            margin_used = pos.get('margin_used', 0)
            
            # 方向 emoji
            side_emoji = "📈" if side == "long" else "📉"
            side_cn = "多" if side == "long" else "空"
            
            # 计算仓位价值
            position_value = size * current_price if current_price else size * entry_price
            total_position_value += position_value
            total_unrealized_pnl += unrealized_pnl
            
            # 计算 PnL 百分比（基于保证金）
            pnl_percent = (unrealized_pnl / margin_used * 100) if margin_used > 0 else 0
            
            # PnL 显示
            pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
            pnl_str = f"${unrealized_pnl:+,.2f} ({pnl_percent:+.2f}%)"
            
            # 仓位信息
            content = f"{side_emoji} **{symbol}** {side_cn} | {leverage}x"
            content += f"\n└ 价值: ${position_value:,.2f} | 入场价: ${entry_price:,.4f}"
            content += f"\n└ {pnl_emoji} 未实现盈亏: {pnl_str}"
            
            # 添加仓位信息
            elements.append({"tag": "markdown", "content": content})
            
            # 添加分割线
            elements.append({"tag": "hr"})
        
        # 移除最后一个分割线
        if elements and elements[-1].get("tag") == "hr":
            elements.pop()
        
        # 汇总统计
        total_pnl_emoji = "🟢" if total_unrealized_pnl >= 0 else "🔴"
        summary = f"**持仓数**: {len(positions)} | **总价值**: ${total_position_value:,.2f}"
        summary += f"\n{total_pnl_emoji} **总未实现盈亏**: ${total_unrealized_pnl:+,.2f}"
        if available_balance is not None:
            summary += f"\n💰 **可用余额**: ${available_balance:,.2f}"
        
        elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": summary})
        
        # 构建完整卡片
        card = {
            "header": {
                "title": {"tag": "plain_text", "content": f"📊 当前仓位 ({len(positions)})"},
                "template": "blue"
            },
            "elements": elements
        }
        
        _send_card_to_user(feishu_client, event.user_id, card)
        
        logger.success(f"[当前仓位] 已发送 {len(positions)} 个仓位信息给用户 {event.user_id}")
        return None
        
    except Exception as e:
        logger.error(f"[当前仓位] 错误: {e}")
        card = build_error_card(f"查询失败: {str(e)}")
        _send_card_to_user(feishu_client, event.user_id, card)
        return None


def _send_card_to_user(feishu_client: FeishuClient, user_id: str, card: dict):
    """发送卡片消息给用户"""
    try:
        success = feishu_client._send_card_via_api(card, user_id)
        if not success:
            logger.warning(f"发送卡片消息失败: user_id={user_id}")
    except Exception as e:
        logger.error(f"发送卡片消息异常: {e}")


# 使用从 feishu_client 导入的卡片构建函数（保持向后兼容）
def _build_success_card(title: str, content: str):
    """构建成功响应卡片"""
    return build_success_card(title, content)


def _build_warning_card(title: str, content: str):
    """构建警告响应卡片"""
    return build_warning_card(title, content)


def _build_error_card(message: str):
    """构建错误响应卡片"""
    return build_error_card(message)


def _build_info_card(title: str, content: str):
    """构建信息响应卡片"""
    return build_info_card(title, content)


def start_callback_server():
    """启动飞书长连接回调服务（使用新仓位推送专用配置）"""
    global feishu_position_client
    
    # 检查配置（使用 feishu_position 配置）
    if not settings.feishu_position.app_id or not settings.feishu_position.app_secret:
        logger.error("错误: 请配置飞书新仓位推送 FEISHU_POSITION_APP_ID 和 FEISHU_POSITION_APP_SECRET")
        return
    
    # 初始化全局飞书客户端（复用实例，避免每次菜单点击都创建）
    feishu_position_client = FeishuClient(
        app_id=settings.feishu_position.app_id,
        app_secret=settings.feishu_position.app_secret
    )
    logger.info("飞书客户端已初始化（用于回调处理）")
    
    # 创建回调客户端（使用 feishu_position 配置）
    callback_client = FeishuCallbackClient(
        app_id=settings.feishu_position.app_id,
        app_secret=settings.feishu_position.app_secret,
        push_url=settings.feishu_position.callback_push_url,
        log_level=settings.feishu_position.callback_log_level
    )
    
    # 注册仓位跟单处理器
    callback_client.register_handler("quick_copy_trade", handle_quick_position_tracking)
    
    # 注册"当前仓位"菜单处理器
    callback_client.register_handler("current-position", handle_current_position)
    
    # 注册全局日志处理器
    def log_all_events(event: CardActionEvent):
        logger.debug(f"[事件日志] action={event.action_tag}, user={event.user_id}, value={event.action_value}")
        return None
    
    callback_client.register_global_handler(log_all_events)
    
    # 启动长连接（阻塞模式）
    logger.info("=" * 50)
    logger.info("飞书长连接回调服务（新仓位推送）")
    logger.info("=" * 50)
    logger.info(f"APP_ID: {settings.feishu_position.app_id[:8]}...")
    logger.info("已注册处理器:")
    logger.info("  - quick_copy_trade: 一键跟单")
    logger.info("  - current-position: 当前仓位菜单")
    logger.info("-" * 50)
    logger.info("正在启动长连接...")
    
    callback_client.start()


async def run():
    """运行仓位跟单机器人"""
    global notifier, db

    setup_logging()

    logger.info("=" * 60)
    logger.info(f"仓位级别跟单机器人 v{VERSION}")
    logger.info("第二种跟单模式：跟单特定仓位")
    logger.info("=" * 60)

    # 初始化数据库
    db = TraderDatabase()

    # 初始化飞书通知器
    notifier = setup_feishu_notifier()
    
    # 初始化 Redis（用于发送/接收开仓通知）
    setup_redis_client()

    # 在后台线程启动飞书回调服务（使用 feishu_position 配置）
    if settings.feishu_position.app_id and settings.feishu_position.app_secret:
        logger.info("启动飞书回调服务...")
        callback_thread = threading.Thread(target=start_callback_server, daemon=True)
        callback_thread.start()
    else:
        logger.warning("飞书新仓位推送未配置，跳过回调服务")

    # 初始化客户端
    if not settings.hyperliquid.private_key:
        logger.error("需要配置 HYPERLIQUID_PRIVATE_KEY")
        return

    client = HyperliquidClient(
        private_key=settings.hyperliquid.private_key,
        wallet_address=settings.hyperliquid.wallet_address,
        testnet=settings.system.testnet_mode
    )

    # 创建仓位跟单机器人（传入 redis_client 接收开仓通知）
    bot = PositionCopyTradingBot(
        client=client,
        check_interval=0.1,  # 检查间隔（秒）
        reload_interval=60.0,  # 配置重载间隔（秒）
        redis_client=redis_client,  # 接收开仓通知
    )

    # 设置回调
    bot.set_on_copy(on_copy_callback)
    bot.set_on_close(on_close_callback)
    bot.set_on_adjust(on_adjust_callback)
    bot.set_on_error(on_error_callback)

    logger.info("启动仓位跟单机器人...")
    logger.info("在 Web 持仓页面点击'跟单此仓位'按钮添加跟单")
    logger.info("或通过飞书消息卡片点击'跟单此仓位'按钮")
    logger.info("按 Ctrl+C 停止\n")

    try:
        await bot.run()
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("\n正在停止...")
        bot.stop()

        # 显示统计
        status = bot.get_status()
        logger.info("\n运行统计:")
        logger.info(f"  跟单数量: {status['tracking_count']}")
        logger.info(f"  活跃: {status['active_count']}")
        logger.info(f"  等待: {status['pending_count']}")

        if status['trackings']:
            logger.info("\n各仓位跟单状态:")
            for t in status['trackings']:
                logger.info(
                    f"  #{t['tracking_id']} | {t['symbol']} | "
                    f"状态: {t['status']} | "
                    f"我方: {t['my_size']:.4f} {t['my_side'] or '-'}"
                )


if __name__ == "__main__":
    # Windows 上需要特殊处理
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("程序已退出")
    
    # 强制退出，避免后台线程阻塞
    os._exit(0)
