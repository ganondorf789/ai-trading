"""
飞书机器人客户端
用于发送交易通知到飞书
"""
import json
import time
from typing import Optional
import requests


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
