"""
数据模型定义

使用 Pydantic 进行类型验证和数据校验
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class FilterConfig(BaseModel):
    """筛选配置"""
    min_pnl: float = Field(default=10000, description="最小总盈亏")
    min_7d_pnl: float = Field(default=0, description="最小近7天盈亏")
    max_drawdown: float = Field(default=0.25, ge=0, le=1, description="最大回撤比例")
    min_sharpe: float = Field(default=1.5, description="最小Sharpe比率")
    min_sortino: float = Field(default=2.5, description="最小Sortino比率")
    min_profit_factor: float = Field(default=1.2, ge=0, description="最小盈亏比")
    min_win_rate: float = Field(default=0.40, ge=0, le=1, description="最小胜率")
    max_win_rate: float = Field(default=0.65, ge=0, le=1, description="最大胜率")
    active_days: int = Field(default=7, ge=0, description="最近N天内有交易")

    @model_validator(mode='after')
    def validate_win_rate_range(self) -> 'FilterConfig':
        """验证胜率范围"""
        if self.min_win_rate > self.max_win_rate:
            raise ValueError(f"min_win_rate ({self.min_win_rate}) 不能大于 max_win_rate ({self.max_win_rate})")
        return self


class GroupCompareConfig(BaseModel):
    """分组对比配置"""
    group_size: int = Field(default=6, ge=2, description="每组人数")
    top_per_group: int = Field(default=2, ge=1, description="每组晋级人数")
    final_size: int = Field(default=6, ge=1, description="决赛最大人数")
    delay: float = Field(default=1.0, ge=0, description="请求间隔（秒）")
    max_retries: int = Field(default=3, ge=1, description="最大重试次数")
    timeout: float = Field(default=60.0, ge=1, description="请求超时（秒）")

    @model_validator(mode='after')
    def validate_group_config(self) -> 'GroupCompareConfig':
        """验证分组配置"""
        if self.top_per_group >= self.group_size:
            raise ValueError(f"top_per_group ({self.top_per_group}) 必须小于 group_size ({self.group_size})")
        return self


class PositionData(BaseModel):
    """持仓数据"""
    coin: str = Field(description="币种")
    szi: float = Field(default=0, description="持仓数量（正多负空）")
    position_value: float = Field(default=0, description="持仓价值")
    unrealized_pnl: float = Field(default=0, description="未实现盈亏")
    return_on_equity: float = Field(default=0, description="ROE")
    leverage_value: float = Field(default=1, ge=1, description="杠杆倍数")
    entry_px: Optional[float] = Field(default=None, description="开仓价格")
    liquidation_px: Optional[float] = Field(default=None, description="清算价格")

    @property
    def direction(self) -> str:
        """持仓方向"""
        return "多" if self.szi > 0 else "空"

    @property
    def direction_en(self) -> str:
        """持仓方向（英文）"""
        return "LONG" if self.szi > 0 else "SHORT"


class CoinStats(BaseModel):
    """币种交易统计"""
    coin: str = Field(description="币种")
    count: int = Field(default=0, ge=0, description="交易次数")
    total_pnl: float = Field(default=0, description="总盈亏")
    win_count: int = Field(default=0, ge=0, description="盈利次数")
    loss_count: int = Field(default=0, ge=0, description="亏损次数")
    avg_pnl: float = Field(default=0, description="平均盈亏")

    @property
    def win_rate(self) -> float:
        """胜率"""
        if self.count == 0:
            return 0
        return self.win_count / self.count


class TraderData(BaseModel):
    """交易员数据"""
    address: str = Field(min_length=42, max_length=42, description="交易员地址")
    overall_score: float = Field(default=0, ge=0, le=100, description="综合评分")
    rating: str = Field(default="", description="评级 (S/A/B/C/D/F)")
    total_pnl: float = Field(default=0, description="总盈亏")
    recent_7d_pnl: float = Field(default=0, description="近7天盈亏")
    recent_30d_pnl: float = Field(default=0, description="近30天盈亏")
    max_drawdown: float = Field(default=0, ge=0, le=1, description="最大回撤")
    sharpe_ratio: float = Field(default=0, description="Sharpe比率")
    sortino_ratio: float = Field(default=0, description="Sortino比率")
    profit_factor: float = Field(default=0, ge=0, description="盈亏比")
    win_rate: float = Field(default=0, ge=0, le=1, description="胜率")
    total_trades: int = Field(default=0, ge=0, description="总交易次数")
    active_days: int = Field(default=0, ge=0, description="活跃天数")
    last_trade_time: Optional[datetime] = Field(default=None, description="最后交易时间")
    account_value: float = Field(default=0, ge=0, description="账户价值")

    # 额外数据（不参与验证）
    positions: List[PositionData] = Field(default_factory=list, description="当前持仓")
    coin_stats: List[CoinStats] = Field(default_factory=list, description="币种统计")
    ai_analysis: Optional[Dict[str, Any]] = Field(default=None, description="AI分析结果")

    @field_validator('address')
    @classmethod
    def validate_address(cls, v: str) -> str:
        """验证以太坊地址格式"""
        if not v.startswith('0x'):
            raise ValueError("地址必须以 0x 开头")
        # 统一为小写
        return v.lower()

    @property
    def short_address(self) -> str:
        """短地址格式"""
        return f"{self.address[:6]}...{self.address[-4:]}"

    class Config:
        extra = "allow"  # 允许额外字段


class AnalysisResult(BaseModel):
    """AI 分析结果"""
    address: str = Field(description="交易员地址")
    summary: str = Field(default="", description="综合评价")
    strengths: List[str] = Field(default_factory=list, description="优势")
    weaknesses: List[str] = Field(default_factory=list, description="弱点")
    trading_style: str = Field(default="", description="交易风格")
    risk_level: str = Field(default="", description="风险等级")
    copy_trading_advice: str = Field(default="", description="跟单建议")
    recommended_allocation: float = Field(default=0, ge=0, le=1, description="建议配置比例")
    ai_provider: str = Field(default="", description="AI提供商")
    analyzed_at: datetime = Field(default_factory=datetime.now, description="分析时间")

    class Config:
        extra = "allow"


class GroupCompareResult(BaseModel):
    """分组对比结果"""
    group_num: int = Field(ge=1, description="组号")
    round_num: int = Field(ge=1, description="轮次")
    total_in_group: int = Field(ge=0, description="组内人数")
    all_traders: List[str] = Field(default_factory=list, description="所有交易员地址")
    winners: List[str] = Field(default_factory=list, description="晋级者地址")
    analysis: str = Field(default="", description="AI分析内容")


class AnalysisMetrics(BaseModel):
    """分析指标统计"""
    total_traders: int = Field(default=0, ge=0, description="总交易员数")
    analyzed: int = Field(default=0, ge=0, description="已分析数")
    failed: int = Field(default=0, ge=0, description="失败数")
    ai_calls: int = Field(default=0, ge=0, description="AI调用次数")
    total_ai_time: float = Field(default=0, ge=0, description="AI总耗时（秒）")
    start_time: Optional[datetime] = Field(default=None, description="开始时间")
    end_time: Optional[datetime] = Field(default=None, description="结束时间")

    def record_analysis(self, success: bool, duration: float):
        """记录一次分析"""
        self.ai_calls += 1
        self.total_ai_time += duration
        if success:
            self.analyzed += 1
        else:
            self.failed += 1

    @property
    def success_rate(self) -> float:
        """成功率"""
        if self.ai_calls == 0:
            return 0
        return self.analyzed / self.ai_calls

    @property
    def avg_ai_time(self) -> float:
        """平均AI耗时"""
        if self.ai_calls == 0:
            return 0
        return self.total_ai_time / self.ai_calls

    @property
    def elapsed_time(self) -> float:
        """总耗时（秒）"""
        if not self.start_time:
            return 0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    def summary(self) -> Dict[str, Any]:
        """返回摘要统计"""
        return {
            'total': self.total_traders,
            'analyzed': self.analyzed,
            'failed': self.failed,
            'success_rate': f"{self.success_rate:.1%}",
            'ai_calls': self.ai_calls,
            'avg_ai_time': f"{self.avg_ai_time:.2f}s",
            'total_time': f"{self.elapsed_time:.1f}s",
        }


class FilteredResult(BaseModel):
    """筛选结果"""
    passed: List[TraderData] = Field(default_factory=list, description="通过筛选的交易员")
    filtered_out: Dict[str, List[TraderData]] = Field(
        default_factory=dict,
        description="被筛除的交易员（按原因分类）"
    )

    @property
    def total_passed(self) -> int:
        return len(self.passed)

    @property
    def total_filtered(self) -> int:
        return sum(len(v) for v in self.filtered_out.values())


class AnalysisReport(BaseModel):
    """分析报告"""
    generated_at: datetime = Field(default_factory=datetime.now, description="生成时间")
    ai_provider: str = Field(default="", description="AI提供商")
    rating: str = Field(default="S", description="筛选评级")
    total_traders_analyzed: int = Field(default=0, ge=0, description="分析交易员数")
    filter_config: Optional[FilterConfig] = Field(default=None, description="筛选配置")
    group_compare_config: Optional[GroupCompareConfig] = Field(default=None, description="分组对比配置")
    comparison_analysis: str = Field(default="", description="综合分析")
    traders: List[Dict[str, Any]] = Field(default_factory=list, description="交易员列表")
    group_compare: Optional[Dict[str, Any]] = Field(default=None, description="分组对比结果")
    metrics: Optional[AnalysisMetrics] = Field(default=None, description="分析指标")

    class Config:
        extra = "allow"
