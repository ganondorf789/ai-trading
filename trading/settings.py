"""
Trading Service 配置管理模块
使用 pydantic-settings 管理环境变量和配置
"""
import os
from typing import Optional, List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class HyperliquidSettings(BaseSettings):
    """Hyperliquid API 配置"""
    model_config = SettingsConfigDict(env_prefix='HYPERLIQUID_')
    
    private_key: str = Field(default="", description="以太坊钱包私钥")
    wallet_address: Optional[str] = Field(
        default=None,
        description="钱包地址（可从私钥派生）"
    )
    testnet: bool = Field(default=False, description="是否使用测试网")


class PostgreSQLSettings(BaseSettings):
    """PostgreSQL 数据库配置"""
    model_config = SettingsConfigDict(env_prefix='POSTGRES_')

    host: str = Field(default="localhost", description="PostgreSQL 主机地址")
    port: int = Field(default=5433, description="PostgreSQL 端口")
    user: str = Field(default="trading", description="数据库用户名")
    password: str = Field(default="trading123", description="数据库密码")
    database: str = Field(default="autotrading", description="数据库名称")

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


class BotSettings(BaseSettings):
    """跟单机器人配置"""
    model_config = SettingsConfigDict(env_prefix='BOT_')
    
    user_id: int = Field(default=1, description="跟单用户ID")
    check_interval: float = Field(default=0.1, description="检查间隔（秒）")
    reload_interval: float = Field(default=60.0, description="配置重载间隔（秒）")


class APISettings(BaseSettings):
    """API 服务配置"""
    model_config = SettingsConfigDict(env_prefix='API_')
    
    key: str = Field(
        default="",
        description="API Key（为空时禁用认证）"
    )
    host: str = Field(
        default="0.0.0.0",
        description="监听地址"
    )
    port: int = Field(
        default=5001,
        description="监听端口"
    )
    debug: bool = Field(
        default=False,
        description="是否启用调试模式"
    )


class LogSettings(BaseSettings):
    """日志配置"""
    model_config = SettingsConfigDict(env_prefix='LOG_')
    
    level: str = Field(default="INFO", description="日志级别")
    dir: str = Field(default="./logs", description="日志目录")


class GRPCSettings(BaseSettings):
    """gRPC 配置"""
    model_config = SettingsConfigDict(env_prefix='GRPC_')
    
    enabled: bool = Field(default=True, description="是否启用 gRPC 模式")
    host: str = Field(default="localhost", description="gRPC 服务器地址")
    port: int = Field(default=50051, description="gRPC 服务器端口")


class Settings:
    """统一配置管理"""
    
    def __init__(self, env_file: str = None):
        """
        初始化配置
        
        Args:
            env_file: 环境变量文件路径，默认为 trading/.env
        """
        # 确定 .env 文件路径
        if env_file is None:
            # 默认使用 trading 目录下的 .env 文件
            current_dir = os.path.dirname(os.path.abspath(__file__))
            env_file = os.path.join(current_dir, '.env')
        
        # 加载 .env 文件
        if os.path.exists(env_file):
            from dotenv import load_dotenv
            load_dotenv(env_file, override=True)
        
        # 初始化各配置模块
        self.hyperliquid = HyperliquidSettings()
        self.postgres = PostgreSQLSettings()
        self.redis = RedisSettings()
        self.bot = BotSettings()
        self.api = APISettings()
        self.log = LogSettings()
        self.grpc = GRPCSettings()
    
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
