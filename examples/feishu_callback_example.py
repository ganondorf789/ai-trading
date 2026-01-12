"""
飞书长连接回调服务

用于接收卡片按钮点击回调，实现一键跟单功能
"""
import sys
import os

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.feishu_client import (
    FeishuCallbackClient,
    CardActionEvent,
)
from config.settings import settings
from database import TraderDatabase

# 初始化数据库
db = TraderDatabase()


def handle_quick_copy_trade(event: CardActionEvent):
    """
    处理一键跟单按钮点击
    
    如果交易员不在跟单列表，则根据默认跟单配置添加到跟单列表，
    并将同步仓位的币种设置为当前币种
    """
    address = event.action_value.get("address", "")
    coin = event.action_value.get("coin", "")
    trader_name = event.action_value.get("trader_name", "")
    
    if not address:
        return _build_error_card("地址信息缺失")
    
    print(f"[跟单回调] 用户 {event.user_id} 请求跟单:")
    print(f"  - 交易员地址: {address}")
    print(f"  - 币种: {coin}")
    print(f"  - 名称: {trader_name}")
    
    try:
        # 检查交易员是否已在跟单列表
        existing = db.get_copy_trading_address(address)
        
        if existing:
            # 已存在
            return _build_warning_card(
                f"该交易员已在跟单列表中",
                f"地址: {address[:16]}..."
            )
        
        # 获取默认跟单配置
        default_config = db.get_default_copy_config()
        
        # 构建新的跟单配置
        new_address_data = {
            'address': address,
            'name': trader_name or "",
            'is_enabled': True,
            'copy_ratio': default_config.get('copy_ratio', 0.1),
            'max_position_size_usd': default_config.get('max_position_size_usd', 500),
            'min_position_size_usd': default_config.get('min_position_size_usd', 20),
            'copy_leverage': default_config.get('copy_leverage', False),
            'max_leverage': default_config.get('max_leverage', 10),
            'default_leverage': default_config.get('default_leverage', 3),
            'slippage': default_config.get('slippage', 0.001),
            'symbols_whitelist': default_config.get('symbols_whitelist', []),
            'symbols_blacklist': default_config.get('symbols_blacklist', []),
            'sync_position': True,  # 启用同步仓位
            'sync_position_symbols': [coin] if coin else [],  # 同步当前币种
            'dry_run': default_config.get('dry_run', False),
        }
        
        # 保存到数据库
        record_id = db.save_copy_trading_address(new_address_data)
        
        if record_id:
            trader_display = trader_name if trader_name else f"{address[:10]}..."
            sync_msg = f"同步币种: {coin}" if coin else "同步所有币种"
            
            print(f"[跟单回调] 添加成功: {trader_display}, {sync_msg}")
            
            return _build_success_card(
                f"已添加 {trader_display} 到跟单列表",
                f"**地址**: `{address[:16]}...`\n**{sync_msg}**\n**跟单比例**: {default_config.get('copy_ratio', 0.1) * 100:.0f}%"
            )
        else:
            return _build_error_card("保存跟单配置失败")
            
    except Exception as e:
        print(f"[跟单回调] 错误: {e}")
        return _build_error_card(f"操作失败: {str(e)}")


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


def start_callback_server():
    """启动长连接回调服务"""
    # 检查配置
    if not settings.feishu.app_id or not settings.feishu.app_secret:
        print("错误: 请配置飞书 APP_ID 和 APP_SECRET")
        return
    
    # 创建回调客户端
    callback_client = FeishuCallbackClient(
        app_id=settings.feishu.app_id,
        app_secret=settings.feishu.app_secret,
        push_url=settings.feishu.callback_push_url,
        log_level=settings.feishu.callback_log_level
    )
    
    # 注册跟单处理器
    callback_client.register_handler("quick_copy_trade", handle_quick_copy_trade)
    
    # 注册全局日志处理器
    def log_all_events(event: CardActionEvent):
        print(f"[事件日志] action={event.action_tag}, user={event.user_id}, value={event.action_value}")
        return None
    
    callback_client.register_global_handler(log_all_events)
    
    # 启动长连接（阻塞模式）
    print("=" * 50)
    print("飞书长连接回调服务")
    print("=" * 50)
    print(f"APP_ID: {settings.feishu.app_id[:8]}...")
    print("已注册处理器: quick_copy_trade")
    print("-" * 50)
    print("正在启动长连接...")
    
    callback_client.start()


if __name__ == "__main__":
    start_callback_server()
