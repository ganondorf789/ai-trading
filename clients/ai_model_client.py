"""
AI模型客户端
支持多个AI提供商：智谱AI、通义千问、Deepseek、OpenRouter
使用官方SDK实现
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from loguru import logger

try:
    from zhipuai import ZhipuAI
except ImportError:
    ZhipuAI = None
    logger.warning("zhipuai SDK not installed. Install with: pip install zhipuai")

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None
    logger.warning("openai SDK not installed. Install with: pip install openai")

try:
    import dashscope
    from dashscope import Generation
except ImportError:
    dashscope = None
    Generation = None
    logger.warning("dashscope SDK not installed. Install with: pip install dashscope")


class BaseAIModelClient(ABC):
    """AI模型客户端基类"""

    def __init__(
        self,
        api_key: str,
        api_url: str,
        model: str,
        timeout: float = 60.0,
        temperature: float = 0.7
    ):
        """
        初始化AI模型客户端

        Args:
            api_key: API密钥
            api_url: API地址
            model: 模型名称
            timeout: 请求超时时间（秒）
            temperature: 生成温度 (0.0-2.0)
        """
        self.api_key = api_key
        self.api_url = api_url
        self.model = model
        self.timeout = timeout
        self.temperature = temperature

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """
        生成文本

        Args:
            prompt: 输入提示词
            **kwargs: 额外参数（如 max_tokens, temperature 等）

        Returns:
            生成的文本
        """
        pass

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        对话接口

        Args:
            messages: 消息列表，格式：[{"role": "user", "content": "..."}]
            **kwargs: 额外参数

        Returns:
            生成的回复
        """
        pass


class ZhipuAIClient(BaseAIModelClient):
    """智谱AI客户端（GLM-4等）- 使用官方SDK"""

    def __init__(self, api_key: str, api_url: str, model: str, **kwargs):
        super().__init__(api_key, api_url, model, **kwargs)

        if ZhipuAI is None:
            raise ImportError(
                "zhipuai SDK is required for ZhipuAIClient. "
                "Install with: pip install zhipuai"
            )

        # 初始化智谱AI客户端
        self.client = ZhipuAI(api_key=api_key)

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本（转换为chat接口调用）"""
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        对话接口

        使用智谱AI官方SDK
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature),
                timeout=kwargs.get("timeout", self.timeout)
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Zhipu AI request failed: {e}")
            raise


class QwenClient(BaseAIModelClient):
    """通义千问客户端 - 使用阿里云DashScope SDK"""

    def __init__(self, api_key: str, api_url: str, model: str, **kwargs):
        super().__init__(api_key, api_url, model, **kwargs)

        if dashscope is None or Generation is None:
            raise ImportError(
                "dashscope SDK is required for QwenClient. "
                "Install with: pip install dashscope"
            )

        # 设置API Key
        dashscope.api_key = api_key

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本（转换为chat接口调用）"""
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        对话接口

        使用阿里云DashScope SDK
        """
        try:
            response = Generation.call(
                model=self.model,
                messages=messages,
                result_format='message',
                temperature=kwargs.get("temperature", self.temperature),
                timeout=kwargs.get("timeout", self.timeout)
            )

            if response.status_code == 200:
                return response.output.choices[0].message.content
            else:
                error_msg = f"Qwen API error: {response.code} - {response.message}"
                logger.error(error_msg)
                raise ValueError(error_msg)

        except Exception as e:
            logger.error(f"Qwen request failed: {e}")
            raise


class DeepseekClient(BaseAIModelClient):
    """Deepseek客户端 - 使用OpenAI兼容SDK"""

    def __init__(self, api_key: str, api_url: str, model: str, **kwargs):
        super().__init__(api_key, api_url, model, **kwargs)

        if OpenAI is None:
            raise ImportError(
                "openai SDK is required for DeepseekClient. "
                "Install with: pip install openai"
            )

        # 初始化OpenAI客户端，指向Deepseek API
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_url,
            timeout=self.timeout
        )

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本（转换为chat接口调用）"""
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        对话接口

        Deepseek使用OpenAI兼容的API
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature)
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"Deepseek request failed: {e}")
            raise


class OpenRouterClient(BaseAIModelClient):
    """OpenRouter客户端 - 使用OpenAI兼容SDK"""

    def __init__(self, api_key: str, api_url: str, model: str, **kwargs):
        super().__init__(api_key, api_url, model, **kwargs)

        if OpenAI is None:
            raise ImportError(
                "openai SDK is required for OpenRouterClient. "
                "Install with: pip install openai"
            )

        # 初始化OpenAI客户端，指向OpenRouter API
        self.client = OpenAI(
            api_key=api_key,
            base_url=api_url,
            timeout=self.timeout,
            default_headers={
                "HTTP-Referer": "https://github.com/auto-trading",
                "X-Title": "Auto Trading System"
            }
        )

    def generate(self, prompt: str, **kwargs) -> str:
        """生成文本（转换为chat接口调用）"""
        return self.chat([{"role": "user", "content": prompt}], **kwargs)

    def chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        """
        对话接口

        OpenRouter使用OpenAI兼容的API
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=kwargs.get("temperature", self.temperature)
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"OpenRouter request failed: {e}")
            raise


class AIModelFactory:
    """AI模型工厂类"""

    _client_map = {
        "zhipu": ZhipuAIClient,
        "qwen": QwenClient,
        "deepseek": DeepseekClient,
        "openrouter": OpenRouterClient
    }

    @classmethod
    def create(
        cls,
        provider: str,
        api_key: str,
        api_url: str,
        model: str,
        **kwargs
    ) -> BaseAIModelClient:
        """
        创建AI客户端实例

        Args:
            provider: 提供商名称 (zhipu, qwen, deepseek, openrouter)
            api_key: API密钥
            api_url: API地址
            model: 模型名称
            **kwargs: 额外参数（timeout, temperature等）

        Returns:
            AI客户端实例

        Raises:
            ValueError: 不支持的提供商
        """
        if provider not in cls._client_map:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Available: {list(cls._client_map.keys())}"
            )

        client_class = cls._client_map[provider]
        return client_class(
            api_key=api_key,
            api_url=api_url,
            model=model,
            **kwargs
        )

    @classmethod
    def create_from_settings(
        cls,
        settings: 'AIModelSettings',
        provider: Optional[str] = None
    ) -> BaseAIModelClient:
        """
        从配置创建客户端

        Args:
            settings: AI模型配置对象
            provider: 提供商名称（默认使用配置中的default_provider）

        Returns:
            AI客户端实例

        Raises:
            ValueError: 无效的提供商或配置错误
        """
        provider = provider or settings.default_provider

        config_map = {
            "zhipu": {
                "api_key": settings.zhipu_api_key,
                "api_url": settings.zhipu_api_url,
                "model": settings.zhipu_model
            },
            "qwen": {
                "api_key": settings.qwen_api_key,
                "api_url": settings.qwen_api_url,
                "model": settings.qwen_model
            },
            "deepseek": {
                "api_key": settings.deepseek_api_key,
                "api_url": settings.deepseek_api_url,
                "model": settings.deepseek_model
            },
            "openrouter": {
                "api_key": settings.openrouter_api_key,
                "api_url": settings.openrouter_api_url,
                "model": settings.openrouter_model
            }
        }

        if provider not in config_map:
            raise ValueError(
                f"Invalid provider: {provider}. "
                f"Available: {list(config_map.keys())}"
            )

        config = config_map[provider]

        # 验证API密钥
        if not config["api_key"]:
            raise ValueError(
                f"API key for {provider} is not configured. "
                f"Please set AI_MODEL_{provider.upper()}_API_KEY in .env"
            )

        return cls.create(
            provider=provider,
            timeout=settings.timeout,
            temperature=settings.temperature,
            **config
        )

    @classmethod
    def get_available_providers(cls) -> List[str]:
        """
        获取支持的提供商列表

        Returns:
            提供商名称列表
        """
        return list(cls._client_map.keys())


def get_ai_client(provider: Optional[str] = None) -> BaseAIModelClient:
    """
    获取AI客户端（使用全局配置）

    这是一个便捷函数，自动从全局配置创建客户端

    Args:
        provider: 提供商名称（可选，默认使用配置中的default_provider）

    Returns:
        AI客户端实例

    Example:
        >>> # 使用默认提供商
        >>> client = get_ai_client()
        >>> response = client.generate("Hello")

        >>> # 指定提供商
        >>> zhipu_client = get_ai_client(provider="zhipu")
    """
    from config.settings import settings
    return AIModelFactory.create_from_settings(settings.ai_model, provider)
