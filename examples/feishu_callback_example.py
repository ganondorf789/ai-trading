"""
飞书长连接回调使用示例

演示如何：
1. 启动长连接接收卡片按钮点击回调
2. 发送带交互按钮的卡片
3. 注册自定义处理器处理特定按钮点击
"""
import sys
import os
import time

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients.feishu_client import (
    FeishuClient,
    FeishuCallbackClient,
    CardActionEvent,
    create_callback_client_from_settings
)
from config.settings import settings


# ============================================================
# 示例 1: 发送带交互按钮的卡片
# ============================================================

def send_trading_card_example():
    """发送跟单确认卡片示例"""
    client = FeishuClient(
        app_id=settings.feishu.app_id,
        app_secret=settings.feishu.app_secret,
        default_user_id=settings.feishu.default_user_id
    )
    
    # 发送带按钮的交互卡片
    client.send_interactive_card(
        title="🔔 新仓位提醒 - BTC",
        content="""**交易员**: Top Trader #1
**币种**: BTC
**方向**: 🟢 做多
**入场价**: $65,000.00
**仓位价值**: $10,000
**杠杆**: 10x""",
        buttons=[
            {
                "text": "✅ 确认跟单",
                "action_tag": "confirm_copy",
                "value": {"coin": "BTC", "side": "long", "trader_id": "123"},
                "type": "primary"
            },
            {
                "text": "❌ 忽略",
                "action_tag": "ignore_position",
                "value": {"coin": "BTC"},
                "type": "danger"
            },
            {
                "text": "📊 查看详情",
                "action_tag": "view_detail",
                "value": {"trader_id": "123"},
                "type": "default"
            }
        ],
        color="green"
    )


# ============================================================
# 示例 2: 启动长连接接收回调
# ============================================================

def handle_confirm_copy(event: CardActionEvent):
    """处理确认跟单按钮点击"""
    coin = event.action_value.get("coin", "")
    side = event.action_value.get("side", "")
    trader_id = event.action_value.get("trader_id", "")
    
    print(f"用户 {event.user_id} 确认跟单:")
    print(f"  - 币种: {coin}")
    print(f"  - 方向: {side}")
    print(f"  - 交易员: {trader_id}")
    
    # 这里可以调用跟单逻辑
    # copy_trading_service.execute_copy(coin, side, trader_id)
    
    # 返回更新后的卡片（可选）
    return {
        "header": {
            "title": {"tag": "plain_text", "content": "✅ 跟单已确认"},
            "template": "green"
        },
        "elements": [
            {
                "tag": "markdown",
                "content": f"**{coin}** 跟单已提交执行"
            }
        ]
    }


def handle_ignore_position(event: CardActionEvent):
    """处理忽略按钮点击"""
    coin = event.action_value.get("coin", "")
    print(f"用户 {event.user_id} 忽略了 {coin} 仓位")
    
    return {
        "header": {
            "title": {"tag": "plain_text", "content": "已忽略"},
            "template": "grey"
        },
        "elements": [
            {"tag": "markdown", "content": "此仓位已被忽略"}
        ]
    }


def start_callback_server():
    """启动长连接回调服务"""
    # 从配置创建客户端
    callback_client = FeishuCallbackClient(
        app_id=settings.feishu.app_id,
        app_secret=settings.feishu.app_secret,
        push_url=settings.feishu.callback_push_url,
        log_level=settings.feishu.callback_log_level
    )
    
    # 注册处理器
    callback_client.register_handler("confirm_copy", handle_confirm_copy)
    callback_client.register_handler("ignore_position", handle_ignore_position)
    
    # 注册全局处理器（记录所有事件）
    def log_all_events(event: CardActionEvent):
        print(f"[LOG] 收到事件: {event.action_tag} from {event.user_id}")
        return None
    
    callback_client.register_global_handler(log_all_events)
    
    # 启动长连接（阻塞模式）
    print("正在启动飞书长连接回调服务...")
    callback_client.start()


def start_callback_server_background():
    """在后台启动长连接回调服务"""
    # 方式 2: 从配置创建客户端
    callback_client = create_callback_client_from_settings()
    
    if callback_client is None:
        print("飞书回调未启用，请检查配置")
        return
    
    # 注册处理器
    callback_client.register_handler("confirm_copy", handle_confirm_copy)
    callback_client.register_handler("ignore_position", handle_ignore_position)
    
    # 后台启动（非阻塞）
    thread = callback_client.start_background()
    
    print("飞书长连接已在后台启动")
    
    # 主程序可以继续执行其他逻辑
    while True:
        time.sleep(1)


# ============================================================
# 示例 3: 配合 Flask 接收推送的事件
# ============================================================

def flask_callback_receiver():
    """Flask 服务接收推送的回调事件"""
    from flask import Flask, request, jsonify
    
    app = Flask(__name__)
    
    @app.route("/feishu/callback", methods=["POST"])
    def handle_feishu_callback():
        """接收飞书回调推送"""
        data = request.json
        
        event_type = data.get("event_type")
        event_data = data.get("data", {})
        
        action_tag = event_data.get("action_tag")
        action_value = event_data.get("action_value", {})
        user_id = event_data.get("user_id")
        
        print(f"收到回调推送:")
        print(f"  - 类型: {event_type}")
        print(f"  - 动作: {action_tag}")
        print(f"  - 值: {action_value}")
        print(f"  - 用户: {user_id}")
        
        # 根据 action_tag 执行相应业务逻辑
        if action_tag == "confirm_copy":
            # 执行跟单
            pass
        elif action_tag == "ignore_position":
            # 忽略仓位
            pass
        
        return jsonify({"status": "ok"})
    
    app.run(host="0.0.0.0", port=8080)


# ============================================================
# 运行示例
# ============================================================

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法:")
        print("  python feishu_callback_example.py send      - 发送交互卡片")
        print("  python feishu_callback_example.py callback  - 启动长连接回调")
        print("  python feishu_callback_example.py receiver  - 启动回调接收服务")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "send":
        send_trading_card_example()
    elif command == "callback":
        start_callback_server()
    elif command == "receiver":
        flask_callback_receiver()
    else:
        print(f"未知命令: {command}")
