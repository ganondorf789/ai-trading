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
from clients.feishu_client import FeishuClient, CopyTradingNotifier, FeishuCallbackClient, CardActionEvent
from engine.position_copy_trading import PositionCopyTradingBot
from config.settings import settings
from database import TraderDatabase


# 全局通知器
notifier: CopyTradingNotifier = None
# 全局数据库
db: TraderDatabase = None


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
            
            return _build_success_card(
                f"已添加 {coin} 仓位跟单",
                f"**目标**: {trader_display}\n**地址**: `{address[:16]}...`\n**跟单比例**: {copy_ratio * 100:.0f}%\n**状态**: 等待开仓"
            )
        else:
            return _build_error_card("保存跟单配置失败")
            
    except Exception as e:
        logger.error(f"[仓位跟单回调] 错误: {e}")
        return _build_error_card(f"操作失败: {str(e)}")


def handle_current_position(event: CardActionEvent):
    """
    处理"当前仓位"菜单点击
    
    获取当前钱包的实时仓位（从 Hyperliquid API），并通过飞书消息发送给用户
    """
    logger.info(f"[当前仓位] 用户 {event.user_id} 查询当前仓位")
    
    # 创建飞书客户端用于发送消息
    feishu_client = FeishuClient(
        app_id=settings.feishu_position.app_id,
        app_secret=settings.feishu_position.app_secret
    )
    
    try:
        # 检查钱包配置
        if not settings.hyperliquid.wallet_address:
            card = _build_error_card("未配置钱包地址 (HYPERLIQUID_WALLET_ADDRESS)")
            _send_card_to_user(feishu_client, event.user_id, card)
            return None
        
        # 创建 Hyperliquid 客户端（只需要读取，不需要私钥）
        client = HyperliquidClient(
            wallet_address=settings.hyperliquid.wallet_address,
            testnet=settings.system.testnet_mode
        )
        
        # 获取当前仓位
        positions = client.get_positions()
        
        if not positions:
            card = _build_info_card(
                "📊 当前仓位",
                "暂无持仓\n\n*钱包地址*: `" + settings.hyperliquid.wallet_address[:16] + "...`"
            )
            _send_card_to_user(feishu_client, event.user_id, card)
            return None
        
        # 构建仓位信息
        content_lines = []
        total_unrealized_pnl = 0.0
        total_position_value = 0.0
        
        for pos in positions:
            # 方向 emoji
            side_emoji = "📈" if pos.side.value == "long" else "📉"
            side_cn = "多" if pos.side.value == "long" else "空"
            
            # 计算仓位价值
            position_value = pos.size * pos.current_price if pos.current_price else pos.size * pos.entry_price
            total_position_value += position_value
            total_unrealized_pnl += pos.unrealized_pnl
            
            # PnL 显示
            pnl_emoji = "🟢" if pos.unrealized_pnl >= 0 else "🔴"
            pnl_str = f"${pos.unrealized_pnl:+,.2f}"
            
            # 基本信息行
            line = f"{side_emoji} **{pos.symbol}** {side_cn} | {pos.leverage}x"
            line += f"\n  └ 数量: {pos.size:.4f} | 价值: ${position_value:,.2f}"
            line += f"\n  └ 入场: ${pos.entry_price:,.4f} | 现价: ${pos.current_price:,.4f}"
            line += f"\n  └ {pnl_emoji} 未实现盈亏: {pnl_str}"
            
            content_lines.append(line)
        
        content = "\n\n".join(content_lines)
        
        # 汇总统计
        total_pnl_emoji = "🟢" if total_unrealized_pnl >= 0 else "🔴"
        content += f"\n\n---\n**持仓数**: {len(positions)} | **总价值**: ${total_position_value:,.2f}"
        content += f"\n{total_pnl_emoji} **总未实现盈亏**: ${total_unrealized_pnl:+,.2f}"
        
        card = _build_info_card(f"📊 当前仓位 ({len(positions)})", content)
        _send_card_to_user(feishu_client, event.user_id, card)
        
        logger.success(f"[当前仓位] 已发送 {len(positions)} 个仓位信息给用户 {event.user_id}")
        return None
        
    except Exception as e:
        logger.error(f"[当前仓位] 错误: {e}")
        card = _build_error_card(f"查询失败: {str(e)}")
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


def _build_success_card(title: str, content: str):
    """构建成功响应卡片"""
    return {
        "header": {
            "title": {"tag": "plain_text", "content": f"✅ {title}"},
            "template": "green"
        },
        "elements": [
            {"tag": "markdown", "content": content}
        ]
    }


def _build_warning_card(title: str, content: str):
    """构建警告响应卡片"""
    return {
        "header": {
            "title": {"tag": "plain_text", "content": f"⚠️ {title}"},
            "template": "orange"
        },
        "elements": [
            {"tag": "markdown", "content": content}
        ]
    }


def _build_error_card(message: str):
    """构建错误响应卡片"""
    return {
        "header": {
            "title": {"tag": "plain_text", "content": "❌ 操作失败"},
            "template": "red"
        },
        "elements": [
            {"tag": "markdown", "content": message}
        ]
    }


def _build_info_card(title: str, content: str):
    """构建信息响应卡片"""
    return {
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "blue"
        },
        "elements": [
            {"tag": "markdown", "content": content}
        ]
    }


def start_callback_server():
    """启动飞书长连接回调服务（使用新仓位推送专用配置）"""
    # 检查配置（使用 feishu_position 配置）
    if not settings.feishu_position.app_id or not settings.feishu_position.app_secret:
        logger.error("错误: 请配置飞书新仓位推送 FEISHU_POSITION_APP_ID 和 FEISHU_POSITION_APP_SECRET")
        return
    
    # 创建回调客户端（使用 feishu_position 配置）
    callback_client = FeishuCallbackClient(
        app_id=settings.feishu_position.app_id,
        app_secret=settings.feishu_position.app_secret,
        push_url=settings.feishu_position.callback_push_url,
        log_level=settings.feishu_position.callback_log_level
    )
    
    # 注册仓位跟单处理器
    callback_client.register_handler("quick_position_tracking", handle_quick_position_tracking)
    
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
    logger.info("已注册处理器: quick_position_tracking, current-position")
    logger.info("-" * 50)
    logger.info("正在启动长连接...")
    
    callback_client.start()


def run_callback_only():
    """仅运行飞书回调服务"""
    global db
    
    setup_logging()
    
    logger.info("=" * 60)
    logger.info(f"仓位跟单 - 飞书回调服务 v{VERSION}")
    logger.info("=" * 60)
    
    # 初始化数据库
    db = TraderDatabase()
    
    start_callback_server()


async def run(with_callback: bool = False):
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

    # 如果需要，在后台线程启动飞书回调服务（使用 feishu_position 配置）
    callback_thread = None
    if with_callback:
        if settings.feishu_position.app_id and settings.feishu_position.app_secret:
            logger.info("同时启动飞书回调服务（新仓位推送配置）...")
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

    # 创建仓位跟单机器人
    bot = PositionCopyTradingBot(
        client=client,
        check_interval=10.0,  # 检查间隔（秒）
        reload_interval=60.0,  # 配置重载间隔（秒）
    )

    # 设置回调
    bot.set_on_copy(on_copy_callback)
    bot.set_on_close(on_close_callback)
    bot.set_on_adjust(on_adjust_callback)
    bot.set_on_error(on_error_callback)

    logger.info("启动仓位跟单机器人...")
    logger.info("在 Web 持仓页面点击'跟单此仓位'按钮添加跟单")
    if with_callback:
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


def print_usage():
    """打印使用说明"""
    print(f"""
仓位级别跟单机器人 v{VERSION}

用法:
    python {sys.argv[0]} [mode]

模式:
    (无参数)  仅运行跟单机器人
    callback  仅运行飞书回调服务
    all       同时运行跟单机器人和飞书回调服务

示例:
    python {sys.argv[0]}           # 仅跟单机器人
    python {sys.argv[0]} callback  # 仅飞书回调
    python {sys.argv[0]} all       # 两者同时运行
""")


if __name__ == "__main__":
    import signal

    # Windows 上需要特殊处理
    if sys.platform == "win32":
        # 设置事件循环策略
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # 解析命令行参数
    mode = sys.argv[1] if len(sys.argv) > 1 else "bot"
    
    if mode in ["-h", "--help", "help"]:
        print_usage()
        sys.exit(0)
    elif mode == "callback":
        # 仅运行飞书回调服务
        try:
            run_callback_only()
        except KeyboardInterrupt:
            logger.info("程序已退出")
    elif mode == "all":
        # 同时运行跟单机器人和飞书回调
        try:
            asyncio.run(run(with_callback=True))
        except KeyboardInterrupt:
            logger.info("程序已退出")
    else:
        # 默认：仅运行跟单机器人
        try:
            asyncio.run(run(with_callback=False))
        except KeyboardInterrupt:
            logger.info("程序已退出")
    
    # 强制退出，避免后台线程阻塞
    os._exit(0)
