"""
飞书机器人客户端
用于发送交易通知到飞书

支持功能：
1. 企业自建应用消息发送
2. 自定义机器人 Webhook
3. 长连接接收用户交互回调（卡片按钮点击等）
"""
import json
import time
import logging
import threading
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import requests

# 尝试导入飞书 SDK（用于长连接回调）
try:
    import lark_oapi as lark
    LARK_SDK_AVAILABLE = True
except ImportError:
    LARK_SDK_AVAILABLE = False
    lark = None


class CardActionType(Enum):
    """卡片交互动作类型"""
    BUTTON_CLICK = "button"          # 按钮点击
    SELECT_CHANGE = "select"         # 下拉选择变更
    DATE_PICKER = "date_picker"      # 日期选择
    INPUT = "input"                  # 输入框
    OVERFLOW = "overflow"            # 折叠按钮组
    UNKNOWN = "unknown"              # 未知类型


@dataclass
class CardActionEvent:
    """卡片交互事件数据"""
    action_type: CardActionType           # 动作类型
    action_tag: str                       # 动作标识（按钮的 action_tag）
    action_value: Dict[str, Any]          # 动作携带的值
    user_id: str                          # 用户 open_id
    user_name: str = ""                   # 用户名称
    message_id: str = ""                  # 消息 ID
    chat_id: str = ""                     # 会话 ID
    chat_type: str = ""                   # 会话类型 (p2p/group)
    tenant_key: str = ""                  # 租户 key
    token: str = ""                       # 用于响应的 token
    timestamp: int = 0                    # 事件时间戳
    raw_event: Dict[str, Any] = field(default_factory=dict)  # 原始事件数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "action_type": self.action_type.value,
            "action_tag": self.action_tag,
            "action_value": self.action_value,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "message_id": self.message_id,
            "chat_id": self.chat_id,
            "chat_type": self.chat_type,
            "tenant_key": self.tenant_key,
            "token": self.token,
            "timestamp": self.timestamp,
        }


# 回调处理函数类型
CardActionHandler = Callable[[CardActionEvent], Optional[Dict[str, Any]]]


class FeishuClient:
    """
    飞书机器人客户端

    支持两种认证方式：
    1. 企业自建应用（App ID + App Secret）
    2. 自定义机器人 Webhook
    """

    def __init__(
        self,
        app_id: str = "",
        app_secret: str = "",
        webhook_url: str = "",
        default_user_id: str = ""
    ):
        """
        初始化飞书客户端

        Args:
            app_id: 飞书应用 App ID
            app_secret: 飞书应用 App Secret
            webhook_url: 自定义机器人 Webhook URL（二选一）
            default_user_id: 默认接收消息的用户 open_id
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.webhook_url = webhook_url
        self.default_user_id = default_user_id

        self.base_url = "https://open.feishu.cn/open-apis"
        self.session = requests.Session()

        # Token 缓存
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def _get_tenant_access_token(self) -> Optional[str]:
        """获取 tenant_access_token"""
        if not self.app_id or not self.app_secret:
            return None

        # 检查缓存
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token

        try:
            url = f"{self.base_url}/auth/v3/tenant_access_token/internal"
            payload = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }

            response = self.session.post(url, json=payload, timeout=10)
            result = response.json()

            if result.get("code") == 0:
                self._access_token = result.get("tenant_access_token")
                expire = result.get("expire", 7200)
                self._token_expires_at = time.time() + expire
                return self._access_token
            else:
                print(f"Feishu: Failed to get token - {result.get('msg')}")
                return None

        except Exception as e:
            print(f"Feishu: Error getting token - {e}")
            return None

    def _get_headers(self) -> Optional[dict]:
        """获取请求头"""
        token = self._get_tenant_access_token()
        if not token:
            return None

        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def send_text(self, text: str, user_id: str = None) -> bool:
        """
        发送文本消息（通过应用）

        Args:
            text: 消息内容
            user_id: 接收者 open_id（默认使用 default_user_id）

        Returns:
            是否发送成功
        """
        recipient = user_id or self.default_user_id
        if not recipient:
            print("Feishu: No recipient specified")
            return False

        headers = self._get_headers()
        if not headers:
            return False

        try:
            url = f"{self.base_url}/im/v1/messages"
            params = {"receive_id_type": "open_id"}

            payload = {
                "receive_id": recipient,
                "msg_type": "text",
                "content": json.dumps({"text": text})
            }

            response = self.session.post(
                url, headers=headers, params=params,
                data=json.dumps(payload), timeout=10
            )
            result = response.json()

            if result.get("code") == 0:
                return True
            else:
                print(f"Feishu: Failed to send - {result.get('msg')}")
                return False

        except Exception as e:
            print(f"Feishu: Error sending message - {e}")
            return False

    def send_webhook(self, text: str) -> bool:
        """
        通过 Webhook 发送消息（自定义机器人）

        Args:
            text: 消息内容

        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            print("Feishu: Webhook URL not configured")
            return False

        try:
            payload = {
                "msg_type": "text",
                "content": {"text": text}
            }

            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            result = response.json()

            if result.get("code") == 0 or result.get("StatusCode") == 0:
                return True
            else:
                print(f"Feishu Webhook: Failed - {result}")
                return False

        except Exception as e:
            print(f"Feishu Webhook: Error - {e}")
            return False

    def send_card(self, title: str, content: str, color: str = "blue") -> bool:
        """
        通过 Webhook 发送卡片消息

        Args:
            title: 卡片标题
            content: 卡片内容（支持 Markdown）
            color: 标题颜色（blue/green/red/orange）

        Returns:
            是否发送成功
        """
        if not self.webhook_url:
            print("Feishu: Webhook URL not configured")
            return False

        color_map = {
            "blue": "blue",
            "green": "green",
            "red": "red",
            "orange": "orange"
        }
        header_color = color_map.get(color, "blue")

        try:
            payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": title
                        },
                        "template": header_color
                    },
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": content
                        }
                    ]
                }
            }

            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            result = response.json()

            if result.get("code") == 0 or result.get("StatusCode") == 0:
                return True
            else:
                print(f"Feishu Card: Failed - {result}")
                return False

        except Exception as e:
            print(f"Feishu Card: Error - {e}")
            return False

    def send_interactive_card(
        self,
        title: str,
        content: str,
        buttons: List[Dict[str, Any]] = None,
        color: str = "blue",
        user_id: str = None
    ) -> bool:
        """
        发送带交互按钮的卡片消息（通过应用 API 发送，支持回调）

        Args:
            title: 卡片标题
            content: 卡片内容（支持 Markdown）
            buttons: 按钮列表，每个按钮为字典：
                - text: 按钮文本
                - action_tag: 动作标识（回调时会返回）
                - value: 附加数据（回调时会返回）
                - type: 按钮类型 (default/primary/danger)
            color: 标题颜色（blue/green/red/orange）
            user_id: 接收者 open_id（通过应用发送时必需）

        Returns:
            是否发送成功
            
        Example:
            ```python
            client.send_interactive_card(
                title="确认跟单",
                content="**币种**: BTC\\n**方向**: 做多",
                buttons=[
                    {"text": "确认", "action_tag": "confirm_copy", "value": {"coin": "BTC"}, "type": "primary"},
                    {"text": "取消", "action_tag": "cancel_copy", "type": "danger"}
                ]
            )
            ```
        """
        color_map = {
            "blue": "blue",
            "green": "green", 
            "red": "red",
            "orange": "orange"
        }
        header_color = color_map.get(color, "blue")

        # 构建卡片元素
        elements = [
            {
                "tag": "markdown",
                "content": content
            }
        ]

        # 添加按钮
        if buttons:
            button_elements = []
            for btn in buttons:
                btn_type = btn.get("type", "default")
                btn_color_map = {
                    "primary": "primary",
                    "danger": "danger",
                    "default": "default"
                }
                
                # 构建按钮的 value（包含 action_tag 以便回调识别）
                btn_value = {
                    "action_tag": btn.get("action_tag", ""),
                    **(btn.get("value", {}) if isinstance(btn.get("value"), dict) else {})
                }
                
                button_elements.append({
                    "tag": "button",
                    "text": {
                        "tag": "plain_text",
                        "content": btn.get("text", "按钮")
                    },
                    "type": btn_color_map.get(btn_type, "default"),
                    "value": btn_value
                })
            
            # 添加按钮行
            elements.append({
                "tag": "action",
                "actions": button_elements
            })

        card = {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title
                },
                "template": header_color
            },
            "elements": elements
        }

        # 如果通过应用 API 发送
        recipient = user_id or self.default_user_id
        if recipient and self.app_id and self.app_secret:
            return self._send_card_via_api(card, recipient)
        
        # 否则通过 Webhook 发送
        if self.webhook_url:
            return self._send_card_via_webhook(card)
        
        print("Feishu: No send method available")
        return False

    def _send_card_via_api(self, card: Dict[str, Any], user_id: str) -> bool:
        """通过应用 API 发送卡片"""
        headers = self._get_headers()
        if not headers:
            return False

        try:
            url = f"{self.base_url}/im/v1/messages"
            params = {"receive_id_type": "open_id"}

            payload = {
                "receive_id": user_id,
                "msg_type": "interactive",
                "content": json.dumps(card)
            }

            response = self.session.post(
                url, headers=headers, params=params,
                data=json.dumps(payload), timeout=10
            )
            result = response.json()

            if result.get("code") == 0:
                return True
            else:
                print(f"Feishu API Card: Failed - {result.get('msg')}")
                return False

        except Exception as e:
            print(f"Feishu API Card: Error - {e}")
            return False

    def _send_card_via_webhook(self, card: Dict[str, Any]) -> bool:
        """通过 Webhook 发送卡片"""
        try:
            payload = {
                "msg_type": "interactive",
                "card": card
            }

            response = self.session.post(
                self.webhook_url,
                json=payload,
                timeout=10
            )
            result = response.json()

            if result.get("code") == 0 or result.get("StatusCode") == 0:
                return True
            else:
                print(f"Feishu Webhook Card: Failed - {result}")
                return False

        except Exception as e:
            print(f"Feishu Webhook Card: Error - {e}")
            return False

    def send(self, text: str, user_id: str = None) -> bool:
        """
        发送消息（自动选择方式）

        优先使用 Webhook，如果没有配置则使用应用发送

        Args:
            text: 消息内容
            user_id: 接收者 open_id（仅应用方式需要）

        Returns:
            是否发送成功
        """
        if self.webhook_url:
            return self.send_webhook(text)
        else:
            return self.send_text(text, user_id)


class CopyTradingNotifier:
    """
    跟单交易通知器

    封装跟单相关的通知消息格式
    """

    def __init__(self, feishu_client: FeishuClient):
        """
        初始化通知器

        Args:
            feishu_client: 飞书客户端实例
        """
        self.feishu = feishu_client

    def notify_copy_open(
        self,
        target_address: str,
        symbol: str,
        side: str,
        size: float,
        price: float = None,
        leverage: int = None
    ) -> bool:
        """
        通知复制开仓

        Args:
            target_address: 目标交易者地址
            symbol: 交易对
            side: 方向 (long/short)
            size: 数量
            price: 价格
            leverage: 杠杆
        """
        side_emoji = "🟢" if side.lower() == "long" else "🔴"
        side_cn = "做多" if side.lower() == "long" else "做空"

        if self.feishu.webhook_url:
            # 使用卡片消息
            content = f"""**目标**: `{target_address[:10]}...`
**交易对**: {symbol}
**方向**: {side_emoji} {side_cn}
**数量**: {size}"""

            if price:
                content += f"\n**价格**: ${price:,.2f}"
            if leverage:
                content += f"\n**杠杆**: {leverage}x"

            return self.feishu.send_card(
                title=f"复制开仓 - {symbol}",
                content=content,
                color="green" if side.lower() == "long" else "red"
            )
        else:
            # 使用文本消息
            msg = f"{side_emoji} 复制开仓\n"
            msg += f"目标: {target_address[:10]}...\n"
            msg += f"交易对: {symbol}\n"
            msg += f"方向: {side_cn}\n"
            msg += f"数量: {size}"

            if price:
                msg += f"\n价格: ${price:,.2f}"
            if leverage:
                msg += f"\n杠杆: {leverage}x"

            return self.feishu.send(msg)

    def notify_copy_close(
        self,
        target_address: str,
        symbol: str,
        pnl: float,
        pnl_percent: float = None
    ) -> bool:
        """
        通知复制平仓

        Args:
            target_address: 目标交易者地址
            symbol: 交易对
            pnl: 盈亏金额
            pnl_percent: 盈亏百分比
        """
        pnl_emoji = "💰" if pnl >= 0 else "💸"
        pnl_color = "green" if pnl >= 0 else "red"

        if self.feishu.webhook_url:
            content = f"""**目标**: `{target_address[:10]}...`
**交易对**: {symbol}
**盈亏**: {pnl_emoji} ${pnl:+,.2f}"""

            if pnl_percent is not None:
                content += f" ({pnl_percent:+.2f}%)"

            return self.feishu.send_card(
                title=f"平仓 - {symbol}",
                content=content,
                color=pnl_color
            )
        else:
            msg = f"{pnl_emoji} 平仓\n"
            msg += f"目标: {target_address[:10]}...\n"
            msg += f"交易对: {symbol}\n"
            msg += f"盈亏: ${pnl:+,.2f}"

            if pnl_percent is not None:
                msg += f" ({pnl_percent:+.2f}%)"

            return self.feishu.send(msg)

    def notify_copy_adjust(
        self,
        target_address: str,
        symbol: str,
        side: str,
        size: float,
        is_increase: bool,
        price: float = None
    ) -> bool:
        """
        通知调整仓位（加仓/减仓）

        Args:
            target_address: 目标交易者地址
            symbol: 交易对
            side: 方向 (long/short)
            size: 调整数量
            is_increase: 是否加仓
            price: 价格
        """
        action = "加仓" if is_increase else "减仓"
        action_emoji = "📈" if is_increase else "📉"
        side_emoji = "🟢" if side.lower() == "long" else "🔴"
        side_cn = "做多" if side.lower() == "long" else "做空"

        if self.feishu.webhook_url:
            content = f"""**目标**: `{target_address[:10]}...`
**交易对**: {symbol}
**操作**: {action_emoji} {action}
**方向**: {side_emoji} {side_cn}
**数量**: {size}"""

            if price:
                content += f"\n**价格**: ${price:,.2f}"

            return self.feishu.send_card(
                title=f"{action} - {symbol}",
                content=content,
                color="blue"
            )
        else:
            msg = f"{action_emoji} {action}\n"
            msg += f"目标: {target_address[:10]}...\n"
            msg += f"交易对: {symbol}\n"
            msg += f"方向: {side_cn}\n"
            msg += f"数量: {size}"

            if price:
                msg += f"\n价格: ${price:,.2f}"

            return self.feishu.send(msg)

    def notify_error(self, error: str, context: str = None) -> bool:
        """
        通知错误

        Args:
            error: 错误信息
            context: 上下文信息
        """
        if self.feishu.webhook_url:
            content = f"**错误**: {error}"
            if context:
                content += f"\n**上下文**: {context}"

            return self.feishu.send_card(
                title="跟单错误",
                content=content,
                color="red"
            )
        else:
            msg = f"跟单错误\n错误: {error}"
            if context:
                msg += f"\n上下文: {context}"

            return self.feishu.send(msg)

    def notify_status(
        self,
        target_count: int,
        total_copies: int,
        successful: int,
        failed: int,
        daily_pnl: float
    ) -> bool:
        """
        通知运行状态摘要

        Args:
            target_count: 跟单目标数
            total_copies: 总复制次数
            successful: 成功次数
            failed: 失败次数
            daily_pnl: 当日盈亏
        """
        pnl_emoji = "📈" if daily_pnl >= 0 else "📉"

        if self.feishu.webhook_url:
            content = f"""**跟单目标**: {target_count}
**总复制**: {total_copies}
**成功**: {successful}
**失败**: {failed}
**当日盈亏**: {pnl_emoji} ${daily_pnl:+,.2f}"""

            return self.feishu.send_card(
                title="跟单状态",
                content=content,
                color="blue"
            )
        else:
            msg = f"跟单状态\n"
            msg += f"跟单目标: {target_count}\n"
            msg += f"总复制: {total_copies}\n"
            msg += f"成功: {successful} / 失败: {failed}\n"
            msg += f"当日盈亏: {pnl_emoji} ${daily_pnl:+,.2f}"

            return self.feishu.send(msg)

    def notify_new_position(
        self,
        address: str,
        position: dict,
        rating: str = None,
        score: float = None,
        trader_name: str = None
    ) -> bool:
        """
        通知新仓位

        Args:
            address: 交易员地址
            position: 仓位数据字典，包含以下字段：
                - coin: 币种
                - szi: 仓位数量（正=多，负=空）
                - entry_px: 入场价格
                - position_value: 仓位价值
                - leverage_value: 杠杆倍数
                - open_time: 开仓时间（可选）
            rating: 交易员评级（如 'S', 'A' 等）
            score: 交易员评分
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

        # 方向判断
        side_emoji = "🟢" if szi > 0 else "🔴"
        side_cn = "做多" if szi > 0 else "做空"

        # 格式化开仓时间
        open_time_str = "未知"
        if open_time:
            try:
                if isinstance(open_time, str):
                    open_time_str = open_time[:19].replace('T', ' ')
            except:
                open_time_str = str(open_time)

        # 交易员显示名称
        trader_display = trader_name if trader_name else f"{address[:10]}..."

        # 评级信息
        rating_info = ""
        if rating:
            if score is not None:
                rating_info = f"\n**评级**: {rating} ({score:.1f}分)"
            else:
                rating_info = f"\n**评级**: {rating}"

        if self.feishu.webhook_url:
            content = f"""**交易员**: `{trader_display}`
**地址**: `{address[:16]}...`{rating_info}
**币种**: {coin}
**方向**: {side_emoji} {side_cn}
**数量**: {abs(szi):.4f}
**入场价**: ${entry_px:,.4f}
**仓位价值**: ${position_value:,.2f}
**杠杆**: {leverage_value}x
**开仓时间**: {open_time_str}"""

            title = f"🆕 新仓位 - {coin} {side_cn}"
            color = "green" if szi > 0 else "red"

            return self.feishu.send_card(title=title, content=content, color=color)
        else:
            msg = f"🆕 新仓位\n"
            msg += f"交易员: {trader_display}\n"
            msg += f"地址: {address[:16]}...\n"
            if rating:
                msg += f"评级: {rating}"
                if score is not None:
                    msg += f" ({score:.1f}分)"
                msg += "\n"
            msg += f"币种: {coin}\n"
            msg += f"方向: {side_emoji} {side_cn}\n"
            msg += f"数量: {abs(szi):.4f}\n"
            msg += f"入场价: ${entry_px:,.4f}\n"
            msg += f"仓位价值: ${position_value:,.2f}\n"
            msg += f"杠杆: {leverage_value}x\n"
            msg += f"开仓时间: {open_time_str}"

            return self.feishu.send(msg)


class FeishuCallbackClient:
    """
    飞书长连接回调客户端
    
    通过 WebSocket 长连接接收用户交互事件（如卡片按钮点击），
    并将事件推送到配置的目标 URL。
    
    使用方式：
    ```python
    callback_client = FeishuCallbackClient(
        app_id="your_app_id",
        app_secret="your_app_secret",
        push_url="http://your-server/callback"
    )
    
    # 注册自定义处理器（可选）
    callback_client.register_handler("copy_trade", handle_copy_trade)
    
    # 启动长连接（阻塞模式）
    callback_client.start()
    
    # 或者后台启动（非阻塞）
    callback_client.start_background()
    ```
    """
    
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        push_url: str = "",
        log_level: str = "INFO"
    ):
        """
        初始化长连接回调客户端
        
        Args:
            app_id: 飞书应用 App ID
            app_secret: 飞书应用 App Secret
            push_url: 回调事件推送的目标 URL
            log_level: 日志级别
        """
        if not LARK_SDK_AVAILABLE:
            raise ImportError(
                "lark-oapi SDK 未安装。请运行: pip install lark-oapi"
            )
        
        self.app_id = app_id
        self.app_secret = app_secret
        self.push_url = push_url
        self.log_level = log_level
        
        # 配置日志
        self.logger = logging.getLogger("FeishuCallback")
        self.logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(handler)
        
        # 自定义处理器 {action_tag: handler}
        self._handlers: Dict[str, CardActionHandler] = {}
        
        # 全局处理器列表（对所有事件触发）
        self._global_handlers: List[CardActionHandler] = []
        
        # WebSocket 客户端
        self._ws_client = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # HTTP Session for pushing events
        self._session = requests.Session()
    
    def register_handler(
        self, 
        action_tag: str, 
        handler: CardActionHandler
    ) -> "FeishuCallbackClient":
        """
        注册特定 action_tag 的处理器
        
        Args:
            action_tag: 卡片按钮的 action_tag 标识
            handler: 处理函数，接收 CardActionEvent，返回可选的响应卡片
            
        Returns:
            self，支持链式调用
        """
        self._handlers[action_tag] = handler
        self.logger.info(f"已注册处理器: {action_tag}")
        return self
    
    def register_global_handler(
        self, 
        handler: CardActionHandler
    ) -> "FeishuCallbackClient":
        """
        注册全局处理器（对所有事件触发）
        
        Args:
            handler: 处理函数
            
        Returns:
            self，支持链式调用
        """
        self._global_handlers.append(handler)
        self.logger.info("已注册全局处理器")
        return self
    
    def _parse_card_action(self, event_data: Any) -> CardActionEvent:
        """
        解析卡片交互事件
        
        Args:
            event_data: 飞书 SDK 的事件数据
            
        Returns:
            CardActionEvent 对象
        """
        try:
            # 获取事件数据
            if hasattr(event_data, 'event'):
                event = event_data.event
            else:
                event = event_data
            
            # 解析 action
            action = {}
            action_tag = ""
            action_value = {}
            action_type = CardActionType.UNKNOWN
            
            if hasattr(event, 'action'):
                action = event.action
                if hasattr(action, 'tag'):
                    tag = action.tag
                    if tag == "button":
                        action_type = CardActionType.BUTTON_CLICK
                    elif tag == "select_static" or tag == "select_person":
                        action_type = CardActionType.SELECT_CHANGE
                    elif tag == "date_picker":
                        action_type = CardActionType.DATE_PICKER
                    elif tag == "input":
                        action_type = CardActionType.INPUT
                    elif tag == "overflow":
                        action_type = CardActionType.OVERFLOW
                
                if hasattr(action, 'value'):
                    # value 可能是字典或字符串
                    raw_value = action.value
                    if isinstance(raw_value, str):
                        try:
                            action_value = json.loads(raw_value)
                        except json.JSONDecodeError:
                            action_value = {"value": raw_value}
                    elif isinstance(raw_value, dict):
                        action_value = raw_value
                    else:
                        action_value = {"value": str(raw_value)}
                    
                    # 提取 action_tag
                    action_tag = action_value.get("action_tag", "")
            
            # 解析用户信息
            user_id = ""
            user_name = ""
            if hasattr(event, 'operator'):
                operator = event.operator
                if hasattr(operator, 'open_id'):
                    user_id = operator.open_id
                if hasattr(operator, 'user_id'):
                    user_id = user_id or operator.user_id
            
            # 解析会话信息
            message_id = ""
            chat_id = ""
            chat_type = ""
            if hasattr(event, 'context'):
                context = event.context
                if hasattr(context, 'open_message_id'):
                    message_id = context.open_message_id
                if hasattr(context, 'open_chat_id'):
                    chat_id = context.open_chat_id
            
            # token
            token = ""
            if hasattr(event, 'token'):
                token = event.token
            
            # tenant_key
            tenant_key = ""
            if hasattr(event_data, 'header') and hasattr(event_data.header, 'tenant_key'):
                tenant_key = event_data.header.tenant_key
            
            return CardActionEvent(
                action_type=action_type,
                action_tag=action_tag,
                action_value=action_value,
                user_id=user_id,
                user_name=user_name,
                message_id=message_id,
                chat_id=chat_id,
                chat_type=chat_type,
                tenant_key=tenant_key,
                token=token,
                timestamp=int(time.time() * 1000),
                raw_event=self._event_to_dict(event_data)
            )
            
        except Exception as e:
            self.logger.error(f"解析卡片事件失败: {e}")
            return CardActionEvent(
                action_type=CardActionType.UNKNOWN,
                action_tag="",
                action_value={},
                user_id="",
                timestamp=int(time.time() * 1000),
                raw_event={}
            )
    
    def _event_to_dict(self, event_data: Any) -> Dict[str, Any]:
        """将事件对象转换为字典"""
        try:
            if hasattr(event_data, '__dict__'):
                return {k: str(v) for k, v in event_data.__dict__.items() 
                        if not k.startswith('_')}
            return {"raw": str(event_data)}
        except:
            return {}
    
    def _push_event(self, event: CardActionEvent) -> bool:
        """
        推送事件到配置的 URL
        
        Args:
            event: 卡片交互事件
            
        Returns:
            是否推送成功
        """
        if not self.push_url:
            self.logger.debug("未配置推送 URL，跳过推送")
            return False
        
        try:
            payload = {
                "event_type": "card_action",
                "timestamp": event.timestamp,
                "data": event.to_dict()
            }
            
            response = self._session.post(
                self.push_url,
                json=payload,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                self.logger.info(
                    f"事件推送成功: action_tag={event.action_tag}, "
                    f"user_id={event.user_id}"
                )
                return True
            else:
                self.logger.warning(
                    f"事件推送失败: status={response.status_code}, "
                    f"response={response.text[:200]}"
                )
                return False
                
        except Exception as e:
            self.logger.error(f"事件推送异常: {e}")
            return False
    
    def _handle_card_action(self, data: Any) -> Optional[Any]:
        """
        处理卡片交互回调
        
        Args:
            data: 飞书推送的事件数据
            
        Returns:
            响应数据（可选，用于更新卡片）
        """
        self.logger.debug(f"收到卡片交互事件")
        
        # 解析事件
        event = self._parse_card_action(data)
        
        self.logger.info(
            f"卡片交互: type={event.action_type.value}, "
            f"tag={event.action_tag}, user={event.user_id}"
        )
        
        # 推送事件到配置的 URL
        self._push_event(event)
        
        # 调用全局处理器
        response_card = None
        for handler in self._global_handlers:
            try:
                result = handler(event)
                if result:
                    response_card = result
            except Exception as e:
                self.logger.error(f"全局处理器执行失败: {e}")
        
        # 调用特定 action_tag 的处理器
        if event.action_tag and event.action_tag in self._handlers:
            try:
                result = self._handlers[event.action_tag](event)
                if result:
                    response_card = result
            except Exception as e:
                self.logger.error(
                    f"处理器 '{event.action_tag}' 执行失败: {e}"
                )
        
        # 返回响应卡片（如果有）
        if response_card:
            return self._build_card_response(response_card)
        
        return None
    
    def _build_card_response(self, card: Dict[str, Any]) -> Any:
        """构建卡片响应"""
        # 返回卡片 JSON 作为响应
        return card
    
    def _build_ws_client(self):
        """构建 WebSocket 客户端"""
        # 构建事件处理器
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            .register_p2_card_action_trigger(self._handle_card_action)
            .build()
        )
        
        # 构建 WebSocket 客户端
        self._ws_client = (
            lark.ws.Client(self.app_id, self.app_secret, 
                          event_handler=event_handler,
                          log_level=lark.LogLevel.DEBUG if self.log_level.upper() == "DEBUG" 
                                    else lark.LogLevel.INFO)
        )
    
    def start(self):
        """
        启动长连接（阻塞模式）
        
        注意：此方法会阻塞当前线程
        """
        if self._running:
            self.logger.warning("长连接已在运行中")
            return
        
        self.logger.info("正在启动飞书长连接...")
        self._running = True
        
        try:
            self._build_ws_client()
            self._ws_client.start()
        except KeyboardInterrupt:
            self.logger.info("收到中断信号，正在停止...")
        except Exception as e:
            self.logger.error(f"长连接异常: {e}")
        finally:
            self._running = False
    
    def start_background(self) -> threading.Thread:
        """
        在后台线程启动长连接（非阻塞模式）
        
        Returns:
            运行中的线程对象
        """
        if self._running:
            self.logger.warning("长连接已在运行中")
            return self._thread
        
        self._thread = threading.Thread(
            target=self.start,
            name="FeishuCallbackThread",
            daemon=True
        )
        self._thread.start()
        self.logger.info("飞书长连接已在后台启动")
        return self._thread
    
    def stop(self):
        """停止长连接"""
        self._running = False
        self.logger.info("飞书长连接已停止")
    
    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running


def create_callback_client_from_settings() -> Optional[FeishuCallbackClient]:
    """
    从配置创建回调客户端
    
    Returns:
        FeishuCallbackClient 实例，如果配置未启用则返回 None
    """
    try:
        from config.settings import settings
        
        if not settings.feishu.callback_enabled:
            return None
        
        if not settings.feishu.app_id or not settings.feishu.app_secret:
            print("Feishu Callback: app_id 或 app_secret 未配置")
            return None
        
        return FeishuCallbackClient(
            app_id=settings.feishu.app_id,
            app_secret=settings.feishu.app_secret,
            push_url=settings.feishu.callback_push_url,
            log_level=settings.feishu.callback_log_level
        )
    except Exception as e:
        print(f"Feishu Callback: 创建客户端失败 - {e}")
        return None
