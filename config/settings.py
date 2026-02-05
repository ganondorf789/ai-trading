"""
配置管理模块
使用 pydantic-settings 管理环境变量和配置
"""
import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgreSQLSettings(BaseSettings):
    """PostgreSQL 数据库配置"""
    model_config = SettingsConfigDict(env_prefix='POSTGRES_')

    host: str = Field(default="localhost", description="PostgreSQL 主机地址")
    port: int = Field(default=5433, description="PostgreSQL 端口")
    user: str = Field(default="trading", description="数据库用户名")
    password: str = Field(default="trading123", description="数据库密码")
    database: str = Field(default="autotrading", description="数据库名称")
    min_connections: int = Field(default=2, description="连接池最小连接数")
    max_connections: int = Field(default=10, description="连接池最大连接数")

    @property
    def dsn(self) -> str:
        """获取数据库连接字符串"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


class RedisSettings(BaseSettings):
    """Redis 配置"""
    model_config = SettingsConfigDict(env_prefix='REDIS_')

    host: str = Field(default="localhost", description="Redis 主机地址")
    port: int = Field(default=6380, description="Redis 端口")
    password: str = Field(default="", description="Redis 密码")
    db: int = Field(default=0, description="Redis 数据库编号")
    max_connections: int = Field(default=10, description="连接池最大连接数")

    @property
    def url(self) -> str:
        """获取 Redis 连接字符串"""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"


class HyperliquidSettings(BaseSettings):
    """Hyperliquid API 配置"""
    model_config = SettingsConfigDict(env_prefix='HYPERLIQUID_')
    
    private_key: str = Field(default="", description="以太坊钱包私钥")
    api_url: str = Field(
        default="https://api.hyperliquid.xyz",
        description="API URL"
    )
    wallet_address: Optional[str] = Field(
        default=None,
        description="钱包地址（可从私钥派生）"
    )
    testnet_api_url: str = Field(
        default="https://api.hyperliquid-testnet.xyz",
        description="测试网 API URL"
    )


class AIModelSettings(BaseSettings):
    """AI模型配置"""
    model_config = SettingsConfigDict(env_prefix='AI_MODEL_')

    # Provider selection
    default_provider: str = Field(default="zhipu", description="默认AI提供商")

    # 智谱AI (GLM)
    zhipu_api_key: str = Field(default="", description="智谱AI API密钥")
    zhipu_model: str = Field(default="glm-4", description="智谱AI模型名称")
    zhipu_api_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4",
        description="智谱AI API地址"
    )

    # 通义千问 (Qwen)
    qwen_api_key: str = Field(default="", description="通义千问 API密钥")
    qwen_model: str = Field(default="qwen-max", description="通义千问模型名称")
    qwen_api_url: str = Field(
        default="https://dashscope.aliyuncs.com/compatible-mode/v1",
        description="通义千问 API地址"
    )

    # Deepseek
    deepseek_api_key: str = Field(default="", description="Deepseek API密钥")
    deepseek_model: str = Field(default="deepseek-chat", description="Deepseek模型名称")
    deepseek_api_url: str = Field(
        default="https://api.deepseek.com/v1",
        description="Deepseek API地址"
    )

    # OpenRouter
    openrouter_api_key: str = Field(default="", description="OpenRouter API密钥")
    openrouter_model: str = Field(
        default="anthropic/claude-3.5-sonnet",
        description="OpenRouter模型名称"
    )
    openrouter_api_url: str = Field(
        default="https://openrouter.ai/api/v1",
        description="OpenRouter API地址"
    )

    # Common settings
    timeout: float = Field(default=60.0, description="API请求超时时间（秒）")
    max_tokens: int = Field(default=4096, description="最大token数")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="生成温度")


class EncryptionSettings(BaseSettings):
    """加密配置"""
    model_config = SettingsConfigDict(env_prefix='ENCRYPTION_')

    secret_key: str = Field(
        default="your-encryption-secret-key-change-this-in-production",
        description="加密密钥（用于加密敏感数据如 api_wallet）"
    )


class JWTSettings(BaseSettings):
    """JWT 认证配置"""
    model_config = SettingsConfigDict(env_prefix='JWT_')

    secret_key: str = Field(
        default="your-jwt-secret-key-change-this-in-production",
        description="JWT 签名密钥"
    )
    algorithm: str = Field(
        default="HS256",
        description="JWT 签名算法"
    )
    access_token_expire_hours: int = Field(
        default=24,
        description="访问令牌过期时间（小时）"
    )
    refresh_token_expire_days: int = Field(
        default=7,
        description="刷新令牌过期时间（天）"
    )


class SystemSettings(BaseSettings):
    """系统配置"""
    model_config = SettingsConfigDict(env_prefix='')
    
    log_level: str = Field(default="INFO", description="日志级别")
    testnet_mode: bool = Field(default=False, description="测试网模式")
    log_dir: str = Field(default="./logs", description="日志目录")
    copy_trading_user_id: int = Field(default=1, description="自动跟单使用的用户ID")


class TradingAPISettings(BaseSettings):
    """Trading API 配置"""
    model_config = SettingsConfigDict(env_prefix='TRADING_API_')
    
    api_key: str = Field(
        default="",
        description="Trading API Key（为空时禁用认证）"
    )
    port: int = Field(
        default=5001,
        description="Trading API 服务端口"
    )


class GRPCServerSettings(BaseSettings):
    """gRPC 服务器配置"""
    model_config = SettingsConfigDict(env_prefix='GRPC_')
    
    host: str = Field(
        default="0.0.0.0",
        description="gRPC 服务器监听地址"
    )
    port: int = Field(
        default=50051,
        description="gRPC 服务器监听端口"
    )
    max_workers: int = Field(
        default=10,
        description="gRPC 服务器最大工作线程数"
    )


class Settings:
    """统一配置管理"""
    
    def __init__(self, env_file: str = ".env"):
        """
        初始化配置
        
        Args:
            env_file: 环境变量文件路径
        """
        # 加载 .env 文件
        if os.path.exists(env_file):
            from dotenv import load_dotenv
            load_dotenv(env_file)
        
        # 初始化各配置模块
        self.postgres = PostgreSQLSettings()
        self.redis = RedisSettings()
        self.hyperliquid = HyperliquidSettings()
        self.ai_model = AIModelSettings()
        self.system = SystemSettings()
        self.encryption = EncryptionSettings()
        self.jwt = JWTSettings()
        self.trading_api = TradingAPISettings()
        self.grpc = GRPCServerSettings()
    
    @property
    def hyperliquid_api_url(self) -> str:
        """获取 Hyperliquid API URL（根据是否测试网）"""
        if self.system.testnet_mode:
            return self.hyperliquid.testnet_api_url
        return self.hyperliquid.api_url
    
    def validate(self) -> bool:
        """验证配置是否有效"""
        errors = []
        
        if not self.hyperliquid.private_key:
            errors.append("HYPERLIQUID_PRIVATE_KEY 未配置")
        
        if errors:
            for error in errors:
                print(f"配置错误: {error}")
            return False
        
        return True


# 全局配置实例
settings = Settings()

