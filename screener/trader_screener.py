"""
Hyperliquid 优质交易者筛选器

自动分析交易者表现并筛选优质地址

重构后的模块化设计:
- models.py: 数据模型
- config.py: 配置管理
- cache.py: 缓存系统
- api_client.py: API 客户端
- metrics_calculator.py: 指标计算
- scorer.py: 评分系统
"""
import asyncio
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from tqdm import tqdm
from loguru import logger
import pendulum

from hyperliquid.info import Info
from hyperliquid.utils import constants

from .models import TraderMetrics, QualityRating
from .config import ScreenerConfig, FilterConfig, ScoringConfig
from .cache import CacheManager, get_cache_manager
from .api_client import SyncAPIClient, AsyncAPIClient, create_api_client
from .metrics_calculator import MetricsCalculator, calculate_metrics
from .scorer import TraderScorer, calculate_scores, get_rating_description
from .utils import (
    SHANGHAI_TZ,
    now_shanghai,
    short_address,
    format_pnl,
    validate_address,
)
from .exceptions import (
    ScreenerError,
    TraderDataError,
    InvalidAddressError,
)

# 飞书通知相关
try:
    from clients.feishu_client import FeishuClient, CopyTradingNotifier
    from config.settings import settings
    FEISHU_AVAILABLE = True
except ImportError:
    FEISHU_AVAILABLE = False


class TraderScreener:
    """
    Hyperliquid 优质交易者筛选器
    
    功能：
    - 获取和分析交易者历史数据
    - 计算多维度质量指标
    - 综合评分和排名
    - 输出优质交易者地址列表
    
    示例:
        ```python
        from screener import TraderScreener, ScreenerConfig
        
        # 使用默认配置
        screener = TraderScreener()
        
        # 或自定义配置
        config = ScreenerConfig()
        config.filter.min_win_rate = 0.5
        config.output.top_n = 10
        screener = TraderScreener(config)
        
        # 分析单个交易者
        metrics = screener.analyze_trader("0x...")
        print(metrics.overall_score)
        
        # 筛选多个交易者
        addresses = ["0x...", "0x...", ...]
        qualified = screener.screen_traders(addresses)
        ```
    """
    
    def __init__(self, config: Optional[ScreenerConfig] = None, cache_fills: bool = True):
        """
        初始化筛选器
        
        Args:
            config: 筛选器配置
            cache_fills: 是否缓存 fills 数据（批量处理时建议设为 False 以节省内存）
        """
        self.config = config or ScreenerConfig()
        
        # 初始化组件
        self._cache = get_cache_manager(self.config.cache)
        self._api_client = SyncAPIClient(self.config.api, self._cache, cache_fills=cache_fills)
        self._metrics_calculator = MetricsCalculator()
        self._scorer = TraderScorer(self.config.scoring)
        
        # 状态存储
        self._analyzed_traders: Dict[str, TraderMetrics] = {}
        self._failed_addresses: List[str] = []
        
        # 数据库连接（用于保存持仓）
        self._db = None
        try:
            from database import TraderDatabase
            self._db = TraderDatabase()
            logger.debug("数据库连接已建立，将自动保存持仓数据")
        except Exception as e:
            logger.warning(f"无法连接数据库，持仓数据将不会保存: {e}")
        
        # 飞书通知器（用于新仓位通知）
        self._notifier = None
        if FEISHU_AVAILABLE:
            try:
                feishu = FeishuClient(
                    app_id=settings.feishu.app_id,
                    app_secret=settings.feishu.app_secret,
                    webhook_url=settings.feishu.webhook_url,
                    default_user_id=settings.feishu.default_user_id
                )
                if feishu.webhook_url or feishu.app_id:
                    self._notifier = CopyTradingNotifier(feishu)
                    logger.debug("飞书通知器已初始化，新仓位将发送通知")
                else:
                    logger.debug("飞书未配置，新仓位通知功能已禁用")
            except Exception as e:
                logger.warning(f"飞书通知器初始化失败: {e}")
        
        api_url = (
            constants.TESTNET_API_URL 
            if self.config.testnet 
            else self.config.api_url
        )
        logger.info(f"交易者筛选器初始化完成，API: {api_url}")
    
    @property
    def cache(self) -> CacheManager:
        """缓存管理器"""
        return self._cache
    
    @property
    def analyzed_count(self) -> int:
        """已分析的交易者数量"""
        return len(self._analyzed_traders)
    
    @property
    def failed_addresses(self) -> List[str]:
        """分析失败的地址列表"""
        return self._failed_addresses.copy()
    
    def analyze_trader(
        self,
        address: str,
        store_fills: bool = True,
        validate: bool = True
    ) -> Optional[TraderMetrics]:
        """
        分析单个交易者
        
        Args:
            address: 交易者地址
            store_fills: 是否在 metrics 中存储原始交易记录
            validate: 是否验证地址格式
        
        Returns:
            TraderMetrics 或 None（分析失败时）
        
        Raises:
            InvalidAddressError: 地址格式无效（仅当 validate=True 时）
        """
        # 地址验证
        if validate and not validate_address(address):
            raise InvalidAddressError(address)
        
        logger.debug(f"分析交易者: {short_address(address)}")
        
        try:
            # 获取用户状态
            user_state = self._api_client.get_user_state(address)
            self._api_client.delay()
            
            # 获取成交记录
            if self.config.lookback_days == 0:
                fills = self._api_client.get_user_fills(
                    address,
                    self.config.max_fills_per_trader
                )
            else:
                start_time = now_shanghai().subtract(days=self.config.lookback_days)
                end_time = now_shanghai()
                fills = self._api_client.get_user_fills_by_time(
                    address,
                    int(start_time.timestamp() * 1000),
                    int(end_time.timestamp() * 1000)
                )
            
            if not fills:
                logger.debug(f"交易者 {short_address(address)} 无成交记录")
                return None
            
            # 从数据库获取总交易数
            db_total_trades = None
            if self._db:
                try:
                    existing_trader = self._db.get_trader_by_address(address)
                    if existing_trader:
                        db_total_trades = existing_trader.get('total_trades')
                except Exception as e:
                    logger.debug(f"获取数据库总交易数失败: {e}")
            
            # 计算指标
            metrics = self._metrics_calculator.calculate(
                address, fills, user_state, store_fills, db_total_trades
            )
            
            # 计算评分
            metrics = self._scorer.calculate_scores(metrics)
            
            # 保存持仓到数据库，并检测新仓位
            if self._db and metrics.asset_positions:
                try:
                    # 先获取旧持仓（用于检测新仓位）
                    old_positions = self._db.get_positions(address)
                    old_coins = {pos['coin'] for pos in old_positions}
                    is_existing_trader = len(old_positions) > 0
                    
                    # 保存新持仓
                    saved_count = self._db.save_positions(address, metrics.asset_positions)
                    logger.debug(f"已保存 {saved_count} 个持仓记录到数据库: {short_address(address)}")
                    
                    # 如果是已存在的交易员（非新交易员），检测新仓位并发送通知
                    if is_existing_trader and self._notifier:
                        # 获取新保存的持仓
                        new_positions = self._db.get_positions(address)
                        new_coins = {pos['coin'] for pos in new_positions}
                        
                        # 检测新仓位
                        new_coin_set = new_coins - old_coins
                        if new_coin_set:
                            logger.info(f"检测到 {len(new_coin_set)} 个新仓位: {short_address(address)}")
                            # 检查交易员是否在跟单列表中，只有不在跟单列表中才发送通知
                            is_in_copy_list = self._db.get_copy_trading_address(address) is not None
                            if is_in_copy_list:
                                logger.info(f"跳过通知（交易员在跟单列表中）: {short_address(address)}")
                            else:
                                # 发送飞书通知
                                for pos in new_positions:
                                    if pos['coin'] in new_coin_set:
                                        rating = metrics.rating.value if metrics else None
                                        score = metrics.overall_score if metrics else None
                                        success = self._notifier.notify_new_position(
                                            address, pos, rating=rating, score=score
                                        )
                                        if success:
                                            logger.info(f"已发送新仓位通知: {short_address(address)} - {pos['coin']}")
                except Exception as e:
                    logger.warning(f"保存持仓到数据库失败 {short_address(address)}: {e}")
            
            # 重建历史仓位记录
            if self._db:
                try:
                    history_count = self._db.rebuild_position_history(address)
                    logger.debug(f"已重建 {history_count} 条历史仓位记录: {short_address(address)}")
                except Exception as e:
                    logger.warning(f"重建历史仓位记录失败 {short_address(address)}: {e}")
            
            # 缓存结果
            self._analyzed_traders[address] = metrics
            
            return metrics
            
        except InvalidAddressError:
            raise
        except Exception as e:
            logger.error(f"分析交易者失败 {short_address(address)}: {e}")
            self._failed_addresses.append(address)
            return None
    
    def analyze_traders(
        self,
        addresses: List[str],
        progress_callback: Optional[Callable] = None,
        show_progress: bool = True
    ) -> List[TraderMetrics]:
        """
        同步分析多个交易者
        
        Args:
            addresses: 交易者地址列表
            progress_callback: 进度回调函数 (current, total, address, metrics)
            show_progress: 是否显示进度条
        
        Returns:
            TraderMetrics 列表
        """
        results = []
        total = len(addresses)
        
        iterator = tqdm(
            enumerate(addresses),
            total=total,
            desc="分析交易者",
            disable=not show_progress
        )
        
        for i, address in iterator:
            metrics = self.analyze_trader(address, validate=False)
            
            if metrics:
                results.append(metrics)
                iterator.set_postfix(
                    qualified=len(results),
                    score=f"{metrics.overall_score:.1f}"
                )
            
            if progress_callback:
                progress_callback(i + 1, total, address, metrics)
            
            # 请求间隔
            if i < total - 1:
                time.sleep(self.config.request_delay)
        
        return results
    
    async def analyze_traders_async(
        self,
        addresses: List[str],
        progress_callback: Optional[Callable] = None
    ) -> List[TraderMetrics]:
        """
        异步分析多个交易者
        
        Args:
            addresses: 交易者地址列表
            progress_callback: 进度回调函数
        
        Returns:
            TraderMetrics 列表
        """
        results = []
        total = len(addresses)
        
        # 创建异步客户端
        async_client = AsyncAPIClient(self.config.api, self._cache)
        semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        
        async def analyze_one(address: str, index: int) -> Optional[TraderMetrics]:
            async with semaphore:
                try:
                    # 获取用户状态
                    user_state = await async_client.get_user_state(address)
                    await async_client.delay()
                    
                    # 获取成交记录
                    if self.config.lookback_days == 0:
                        fills = await async_client.get_user_fills(
                            address,
                            self.config.max_fills_per_trader
                        )
                    else:
                        start_time = now_shanghai().subtract(
                            days=self.config.lookback_days
                        )
                        end_time = now_shanghai()
                        fills = await async_client.get_user_fills_by_time(
                            address,
                            int(start_time.timestamp() * 1000),
                            int(end_time.timestamp() * 1000)
                        )
                    
                    if not fills:
                        return None
                    
                    # 计算指标
                    metrics = self._metrics_calculator.calculate(
                        address, fills, user_state, store_fills=True
                    )
                    
                    # 计算评分
                    metrics = self._scorer.calculate_scores(metrics)
                    
                    # 保存持仓到数据库
                    if self._db and metrics.asset_positions:
                        try:
                            saved_count = self._db.save_positions(address, metrics.asset_positions)
                            logger.debug(f"已保存 {saved_count} 个持仓记录到数据库: {short_address(address)}")
                        except Exception as e:
                            logger.warning(f"保存持仓到数据库失败 {short_address(address)}: {e}")
                    
                    # 缓存结果
                    self._analyzed_traders[address] = metrics
                    
                    if progress_callback:
                        progress_callback(index + 1, total, address, metrics)
                    
                    await asyncio.sleep(self.config.request_delay)
                    return metrics
                    
                except Exception as e:
                    logger.error(f"异步分析失败 {short_address(address)}: {e}")
                    self._failed_addresses.append(address)
                    return None
        
        try:
            tasks = [
                analyze_one(addr, i)
                for i, addr in enumerate(addresses)
            ]
            
            results_raw = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results_raw:
                if isinstance(result, TraderMetrics):
                    results.append(result)
        finally:
            await async_client.close()
        
        return results
    
    def _passes_filters(self, metrics: TraderMetrics) -> bool:
        """
        检查交易者是否通过筛选条件
        
        Args:
            metrics: 交易者指标
        
        Returns:
            是否通过筛选
        """
        f = self.config.filter
        
        if metrics.total_trades < f.min_total_trades:
            return False
        
        if metrics.win_rate < f.min_win_rate:
            return False
        
        if metrics.profit_factor < f.min_profit_factor:
            return False
        
        if metrics.total_pnl < f.min_total_pnl:
            return False
        
        if metrics.max_drawdown > f.max_drawdown:
            return False
        
        if metrics.active_days < f.min_active_days:
            return False
        
        if metrics.sharpe_ratio < f.min_sharpe_ratio:
            return False
        
        return True
    
    def screen_traders(
        self,
        addresses: List[str],
        progress_callback: Optional[Callable] = None,
        show_progress: bool = True
    ) -> List[TraderMetrics]:
        """
        筛选优质交易者
        
        Args:
            addresses: 候选交易者地址列表
            progress_callback: 进度回调
            show_progress: 是否显示进度条
        
        Returns:
            符合条件的交易者列表（按评分排序）
        """
        logger.info(f"开始筛选 {len(addresses)} 个交易者...")
        
        # 分析所有交易者
        all_metrics = self.analyze_traders(
            addresses, progress_callback, show_progress
        )
        
        # 筛选符合条件的
        qualified = [m for m in all_metrics if self._passes_filters(m)]
        
        # 按评分排序
        qualified.sort(key=lambda x: x.overall_score, reverse=True)
        
        # 取前 N 名
        top_traders = qualified[:self.config.top_n]
        
        logger.info(f"筛选完成: {len(top_traders)}/{len(addresses)} 个优质交易者")
        
        return top_traders
    
    async def screen_traders_async(
        self,
        addresses: List[str],
        progress_callback: Optional[Callable] = None
    ) -> List[TraderMetrics]:
        """
        异步筛选优质交易者
        
        Args:
            addresses: 候选交易者地址列表
            progress_callback: 进度回调
        
        Returns:
            符合条件的交易者列表（按评分排序）
        """
        logger.info(f"开始异步筛选 {len(addresses)} 个交易者...")
        
        all_metrics = await self.analyze_traders_async(addresses, progress_callback)
        
        qualified = [m for m in all_metrics if self._passes_filters(m)]
        qualified.sort(key=lambda x: x.overall_score, reverse=True)
        
        top_traders = qualified[:self.config.top_n]
        
        logger.info(f"筛选完成: {len(top_traders)}/{len(addresses)} 个优质交易者")
        
        return top_traders
    
    def save_results(
        self,
        traders: List[TraderMetrics],
        filepath: Optional[str] = None,
        include_fills: bool = False
    ) -> None:
        """
        保存筛选结果
        
        Args:
            traders: 交易者列表
            filepath: 输出文件路径
            include_fills: 是否包含原始交易记录
        """
        filepath = filepath or self.config.output_file
        
        output = {
            "timestamp": now_shanghai().to_iso8601_string(),
            "config": {
                "lookback_days": self.config.lookback_days,
                "min_total_trades": self.config.min_total_trades,
                "min_win_rate": self.config.min_win_rate,
                "min_profit_factor": self.config.min_profit_factor,
            },
            "total_analyzed": len(self._analyzed_traders),
            "qualified_count": len(traders),
            "traders": [
                t.to_flat_dict(include_fills=include_fills)
                for t in traders
            ]
        }
        
        # 确保目录存在
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
        
        logger.info(f"结果已保存至: {filepath}")
    
    def print_summary(
        self,
        traders: List[TraderMetrics],
        detailed: bool = False
    ) -> None:
        """
        打印筛选结果摘要
        
        Args:
            traders: 交易者列表
            detailed: 是否显示详细信息
        """
        logger.info("\n" + "=" * 120)
        logger.info("Hyperliquid 优质交易者筛选结果")
        logger.info("=" * 120)
        logger.info(f"分析时间 (上海时区): {now_shanghai().format('YYYY-MM-DD HH:mm:ss')}")
        logger.info(
            f"筛选条件: 胜率≥{self.config.min_win_rate:.0%}, "
            f"盈亏比≥{self.config.min_profit_factor:.1f}, "
            f"交易次数≥{self.config.min_total_trades}"
        )
        logger.info("-" * 120)
        
        if not traders:
            logger.warning("未找到符合条件的交易者")
            return
        
        # 主要指标表格
        header = (
            f"{'#':<3} {'等级':<3} {'地址':<14} {'评分':<6} {'胜率':<7} "
            f"{'盈亏比':<7} {'总PnL':<11} {'交易数':<6} {'回撤':<6} "
            f"{'Sharpe':<7} {'活跃天':<6} {'杠杆':<5} {'持仓':<4}"
        )
        logger.info(header)
        logger.info("-" * 120)
        
        for i, t in enumerate(traders, 1):
            addr_short = short_address(t.address)
            pnl_str = format_pnl(t.total_pnl)
            pf_str = (
                f"{t.profit_factor:.2f}"
                if t.profit_factor != float('inf')
                else "∞"
            )
            sharpe_str = f"{t.sharpe_ratio:.2f}" if t.sharpe_ratio else "N/A"
            
            row = (
                f"{i:<3} {t.rating.value:<3} {addr_short:<14} "
                f"{t.overall_score:>5.1f} {t.win_rate:>6.1%} "
                f"{pf_str:>6} {pnl_str:>10} {t.total_trades:>5} "
                f"{t.max_drawdown:>5.1%} {sharpe_str:>6} "
                f"{t.active_days:>5} {t.avg_leverage:>4.0f}x {t.current_positions:>3}"
            )
            logger.info(row)
        
        logger.info("=" * 120)
        
        # 详细信息
        if detailed:
            self._print_detailed_info(traders)
        
        # 推荐列表
        self._print_recommendations(traders)
    
    def _print_detailed_info(self, traders: List[TraderMetrics]) -> None:
        """打印详细指标信息"""
        logger.info("\n详细指标:")
        logger.info("-" * 120)
        
        for i, t in enumerate(traders, 1):
            last_trade = (
                t.last_trade_time.format('MM-DD HH:mm')
                if t.last_trade_time else "N/A"
            )
            
            logger.info(f"\n[{i}] {t.address}")
            logger.info(
                f"    基础: 胜率={t.win_rate:.1%}, 盈亏比={t.profit_factor:.2f}, "
                f"总PnL={format_pnl(t.total_pnl)}, 交易数={t.total_trades}"
            )
            logger.info(
                f"    风险: Sharpe={t.sharpe_ratio:.2f}, Sortino={t.sortino_ratio:.2f}, "
                f"回撤={t.max_drawdown:.1%}, 最大单亏={format_pnl(-t.max_single_loss)}"
            )
            logger.info(
                f"    VaR: 95%={format_pnl(-t.risk.var_95)}, "
                f"99%={format_pnl(-t.risk.var_99)}, "
                f"CVaR95%={format_pnl(-t.risk.cvar_95)}"
            )
            logger.info(
                f"    活跃: 活跃天={t.active_days}, 最后交易={last_trade}, "
                f"杠杆={t.avg_leverage:.0f}x, 持仓数={t.current_positions}"
            )
            logger.info(
                f"    交易: 平均价格={format_pnl(t.avg_trade_price)}, "
                f"平均规模={format_pnl(t.avg_trade_size)}, "
                f"连赢={t.max_consecutive_wins}, 连亏={t.max_consecutive_losses}"
            )
            logger.info(
                f"    偏好: 品种数={t.unique_symbols}, "
                f"最爱={t.favorite_symbol or 'N/A'}, "
                f"多空比={t.long_short_ratio:.1%}"
            )
            logger.info(
                f"    近7天: PnL={format_pnl(t.recent_7d_pnl)}, "
                f"胜率={t.recent_7d_win_rate:.1%}"
            )
            logger.info(
                f"    平均盈利={format_pnl(t.avg_win_amount)}, "
                f"平均亏损={format_pnl(-t.avg_loss_amount)}"
            )
    
    def _print_recommendations(self, traders: List[TraderMetrics]) -> None:
        """打印推荐列表"""
        logger.info(f"\n建议跟单的交易者地址 (评级 A 及以上):")
        
        for trader in traders:
            if trader.rating in [QualityRating.S_TIER, QualityRating.A_TIER]:
                last_trade = (
                    trader.last_trade_time.format('MM-DD')
                    if trader.last_trade_time else "N/A"
                )
                logger.info(
                    f"  [{trader.rating.value}] {trader.address} "
                    f"(胜率:{trader.win_rate:.0%}, PnL:{format_pnl(trader.total_pnl)}, "
                    f"最后:{last_trade})"
                )
        
        logger.info("")
    
    def get_sample_addresses(self) -> List[str]:
        """
        获取示例交易者地址（用于测试）
        
        Returns:
            示例地址列表
        """
        # 这些是公开的测试地址，实际使用时需要替换
        return []
    
    def clear_cache(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._analyzed_traders.clear()
        self._failed_addresses.clear()
        logger.debug("缓存已清空")
    
    def clear_fills_cache(self) -> None:
        """仅清空 fills 缓存（释放大量内存）"""
        self._cache.clear('fills')
        logger.debug("fills 缓存已清空")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计
        
        Returns:
            缓存统计字典
        """
        return self._cache.get_stats()


def discover_active_traders(
    info: Optional[Info] = None,
    sample_symbols: Optional[List[str]] = None,
    limit_per_symbol: int = 50,
    min_volume_usd: float = 10000.0
) -> List[str]:
    """
    发现活跃交易者
    
    通过监控最近交易来发现活跃的交易者地址
    
    Args:
        info: Hyperliquid Info 客户端
        sample_symbols: 要监控的交易对
        limit_per_symbol: 每个交易对获取的交易数
        min_volume_usd: 最小交易量筛选
    
    Returns:
        活跃交易者地址列表
    """
    if info is None:
        info = Info(constants.MAINNET_API_URL, skip_ws=True)
    
    sample_symbols = sample_symbols or ['BTC', 'ETH', 'SOL', 'ARB', 'DOGE']
    traders = set()
    
    logger.info(f"发现活跃交易者，监控交易对: {sample_symbols}")
    
    for symbol in sample_symbols:
        try:
            # 尝试获取最近交易
            if hasattr(info, 'recent_trades'):
                recent_trades = info.recent_trades(symbol)
                
                for trade in recent_trades[:limit_per_symbol]:
                    volume = float(trade.get('px', 0)) * float(trade.get('sz', 0))
                    if volume >= min_volume_usd:
                        users = trade.get('users', [None, None])
                        if users[0]:
                            traders.add(users[0])
                        if users[1]:
                            traders.add(users[1])
            
            time.sleep(0.3)  # 避免频率限制
            
        except Exception as e:
            logger.warning(f"获取 {symbol} 交易失败: {e}")
    
    logger.info(f"发现 {len(traders)} 个活跃交易者")
    return list(traders)


# 便捷函数
def quick_analyze(
    address: str,
    config: Optional[ScreenerConfig] = None
) -> Optional[TraderMetrics]:
    """
    快速分析单个交易者
    
    Args:
        address: 交易者地址
        config: 筛选器配置
    
    Returns:
        TraderMetrics 或 None
    """
    screener = TraderScreener(config)
    return screener.analyze_trader(address)


def quick_screen(
    addresses: List[str],
    config: Optional[ScreenerConfig] = None,
    show_progress: bool = True
) -> List[TraderMetrics]:
    """
    快速筛选交易者
    
    Args:
        addresses: 交易者地址列表
        config: 筛选器配置
        show_progress: 是否显示进度
    
    Returns:
        符合条件的交易者列表
    """
    screener = TraderScreener(config)
    return screener.screen_traders(addresses, show_progress=show_progress)
