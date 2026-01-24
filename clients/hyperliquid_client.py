"""
Hyperliquid API 客户端
用于获取实时数据和执行交易
"""
import asyncio
import time
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Callable
import eth_account
from loguru import logger

from hyperliquid.info import Info
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

from core.models import (
    OHLCV, OHLCVDataFrame, Ticker, Order, Position, Trade,
    AccountInfo, OrderSide, OrderType, OrderStatus, PositionSide
)


class HyperliquidClient:
    """
    Hyperliquid API 客户端
    
    用于：
    - 获取实时市场数据
    - 订阅 WebSocket 数据流
    - 执行交易订单
    - 管理持仓
    """
    
    def __init__(
        self,
        private_key: Optional[str] = None,
        wallet_address: Optional[str] = None,
        api_url: str = constants.MAINNET_API_URL,
        testnet: bool = False
    ):
        """
        初始化 Hyperliquid 客户端

        Args:
            private_key: 以太坊钱包私钥（交易需要）
            wallet_address: 钱包地址（用于查询，可选）
            api_url: API URL
            testnet: 是否使用测试网
        """
        self.testnet = testnet
        self.api_url = constants.TESTNET_API_URL if testnet else api_url

        # 初始化 Info 客户端（只读）
        self.info = Info(self.api_url, skip_ws=True)
        self.info_ws = None  # WebSocket 订阅用

        # 初始化 Exchange 客户端（交易用）
        self.exchange: Optional[Exchange] = None
        self.wallet: Optional[eth_account.Account] = None
        self.wallet_address: Optional[str] = wallet_address

        if private_key:
            self._init_trading(private_key)

        # 缓存
        self._meta_cache: Optional[Dict] = None
        self._asset_map: Dict[str, int] = {}

        # 回调函数
        self._callbacks: Dict[str, List[Callable]] = {}
    
    def _init_trading(self, private_key: str):
        """初始化交易功能"""
        try:
            self.wallet = eth_account.Account.from_key(private_key)
            # 如果没有预先配置钱包地址，则从私钥派生
            if not self.wallet_address:
                self.wallet_address = self.wallet.address
            self.exchange = Exchange(self.wallet, self.api_url)
            logger.info(f"交易功能已初始化，钱包地址: {self.wallet_address}")
        except Exception as e:
            logger.error(f"初始化交易功能失败: {e}")
            raise
    
    # ==================== 市场数据 ====================
    
    def get_meta(self) -> Dict[str, Any]:
        """
        获取市场元数据
        
        Returns:
            市场元数据（交易对信息等）
        """
        if self._meta_cache is None:
            self._meta_cache = self.info.meta()
            # 构建资产映射
            for idx, asset in enumerate(self._meta_cache.get('universe', [])):
                self._asset_map[asset['name']] = idx
        return self._meta_cache
    
    def get_all_mids(self) -> Dict[str, float]:
        """
        获取所有交易对的中间价
        
        Returns:
            {symbol: mid_price} 字典
        """
        return self.info.all_mids()
    
    def get_mid_price(self, symbol: str) -> float:
        """
        获取指定交易对的中间价
        
        Args:
            symbol: 交易对符号
        
        Returns:
            中间价
        """
        mids = self.get_all_mids()
        return float(mids.get(symbol, 0))
    
    def get_l2_orderbook(self, symbol: str) -> Dict[str, Any]:
        """
        获取 L2 订单簿
        
        Args:
            symbol: 交易对符号
        
        Returns:
            订单簿数据
        """
        return self.info.l2_snapshot(symbol)
    
    def get_ticker(self, symbol: str) -> Ticker:
        """
        获取行情数据
        
        Args:
            symbol: 交易对符号
        
        Returns:
            Ticker 对象
        """
        orderbook = self.get_l2_orderbook(symbol)
        bids, asks = orderbook.get('levels', [[], []])
        
        best_bid = float(bids[0]['px']) if bids else 0
        best_ask = float(asks[0]['px']) if asks else 0
        
        # 获取24小时交易量
        meta_ctx = self.info.meta_and_asset_ctxs()
        _, contexts = meta_ctx
        
        volume_24h = 0
        meta = self.get_meta()
        for idx, asset in enumerate(meta.get('universe', [])):
            if asset['name'] == symbol and idx < len(contexts):
                volume_24h = float(contexts[idx].get('dayNtlVlm', 0))
                break
        
        return Ticker(
            symbol=symbol,
            bid=best_bid,
            ask=best_ask,
            last=(best_bid + best_ask) / 2,
            volume_24h=volume_24h,
            timestamp=datetime.now()
        )
    
    def get_candles(
        self,
        symbol: str,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[OHLCV]:
        """
        获取 K 线数据
        
        Args:
            symbol: 交易对符号
            interval: 时间间隔 (1m, 5m, 15m, 1h, 4h, 1d)
            start_time: 开始时间
            end_time: 结束时间
        
        Returns:
            OHLCV 数据列表
        """
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(days=1)
        
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        candles = self.info.candles_snapshot(
            symbol, interval, start_ms, end_ms
        )
        
        ohlcv_list = []
        for candle in candles:
            ohlcv = OHLCV(
                timestamp=datetime.fromtimestamp(candle['t'] / 1000),
                open=float(candle['o']),
                high=float(candle['h']),
                low=float(candle['l']),
                close=float(candle['c']),
                volume=float(candle['v'])
            )
            ohlcv_list.append(ohlcv)
        
        ohlcv_list.sort(key=lambda x: x.timestamp)
        return ohlcv_list
    
    def get_candles_dataframe(
        self,
        symbol: str,
        interval: str = "1h",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> OHLCVDataFrame:
        """获取 K 线数据 DataFrame"""
        candles = self.get_candles(symbol, interval, start_time, end_time)
        return OHLCVDataFrame(candles)
    
    # ==================== WebSocket 订阅 ====================
    
    def _ensure_ws_info(self):
        """确保 WebSocket Info 客户端已初始化"""
        if self.info_ws is None:
            self.info_ws = Info(self.api_url, skip_ws=False)
    
    def subscribe_trades(self, symbol: str, callback: Callable):
        """
        订阅交易数据
        
        Args:
            symbol: 交易对符号
            callback: 回调函数
        """
        self._ensure_ws_info()
        self.info_ws.subscribe(
            {"type": "trades", "coin": symbol},
            callback
        )
        logger.info(f"已订阅 {symbol} 交易数据")
    
    def subscribe_orderbook(self, symbol: str, callback: Callable):
        """
        订阅订单簿数据
        
        Args:
            symbol: 交易对符号
            callback: 回调函数
        """
        self._ensure_ws_info()
        self.info_ws.subscribe(
            {"type": "l2Book", "coin": symbol},
            callback
        )
        logger.info(f"已订阅 {symbol} 订单簿数据")
    
    def subscribe_candles(self, symbol: str, interval: str, callback: Callable):
        """
        订阅 K 线数据
        
        Args:
            symbol: 交易对符号
            interval: 时间间隔
            callback: 回调函数
        """
        self._ensure_ws_info()
        self.info_ws.subscribe(
            {"type": "candle", "coin": symbol, "interval": interval},
            callback
        )
        logger.info(f"已订阅 {symbol} {interval} K线数据")
    
    def subscribe_all_mids(self, callback: Callable):
        """
        订阅所有中间价
        
        Args:
            callback: 回调函数
        """
        self._ensure_ws_info()
        self.info_ws.subscribe({"type": "allMids"}, callback)
        logger.info("已订阅所有中间价")
    
    def subscribe_user_events(self, callback: Callable):
        """
        订阅用户事件（成交、清算等）
        
        Args:
            callback: 回调函数
        """
        if not self.wallet_address:
            raise ValueError("需要先初始化钱包")
        
        self._ensure_ws_info()
        self.info_ws.subscribe(
            {"type": "userEvents", "user": self.wallet_address},
            callback
        )
        logger.info("已订阅用户事件")
    
    # ==================== 账户信息 ====================
    
    def get_user_state(self) -> Dict[str, Any]:
        """
        获取用户状态
        
        Returns:
            用户状态数据
        """
        if not self.wallet_address:
            raise ValueError("需要先初始化钱包")
        return self.info.user_state(self.wallet_address)
    
    def get_account_info(self) -> AccountInfo:
        """
        获取账户信息
        
        Returns:
            AccountInfo 对象
        """
        state = self.get_user_state()
        margin = state.get('marginSummary', {})
        
        positions = []
        for pos_data in state.get('assetPositions', []):
            pos = pos_data.get('position', {})
            if float(pos.get('szi', 0)) != 0:
                size = float(pos.get('szi', 0))
                positions.append(Position(
                    symbol=pos.get('coin', ''),
                    side=PositionSide.LONG if size > 0 else PositionSide.SHORT,
                    size=abs(size),
                    entry_price=float(pos.get('entryPx', 0)),
                    current_price=float(pos.get('markPx', 0)) if 'markPx' in pos else 0,
                    leverage=int(pos.get('leverage', {}).get('value', 1)),
                    unrealized_pnl=float(pos.get('unrealizedPnl', 0)),
                    liquidation_price=float(pos.get('liquidationPx', 0)) if pos.get('liquidationPx') else None,
                    margin_used=float(pos.get('marginUsed', 0))
                ))
        
        return AccountInfo(
            balance=float(margin.get('accountValue', 0)),
            equity=float(margin.get('accountValue', 0)),
            available_margin=float(state.get('withdrawable', 0)),
            used_margin=float(margin.get('totalMarginUsed', 0)),
            unrealized_pnl=sum(p.unrealized_pnl for p in positions),
            realized_pnl=0,  # 需要从历史计算
            positions=positions
        )
    
    def get_positions(self) -> List[Position]:
        """
        获取当前持仓
        
        Returns:
            持仓列表
        """
        return self.get_account_info().positions
    
    def get_open_orders(self) -> List[Order]:
        """
        获取未成交订单
        
        Returns:
            订单列表
        """
        if not self.wallet_address:
            raise ValueError("需要先初始化钱包")
        
        orders_data = self.info.open_orders(self.wallet_address)
        orders = []
        
        for order_data in orders_data:
            orders.append(Order(
                id=str(order_data.get('oid', '')),
                symbol=order_data.get('coin', ''),
                side=OrderSide.BUY if order_data.get('side') == 'B' else OrderSide.SELL,
                order_type=OrderType.LIMIT,
                size=float(order_data.get('sz', 0)),
                price=float(order_data.get('limitPx', 0)),
                status=OrderStatus.OPEN,
                created_at=datetime.fromtimestamp(order_data.get('timestamp', 0) / 1000)
            ))
        
        return orders
    
    def get_user_fills(self, limit: int = 100) -> List[Trade]:
        """
        获取成交历史
        
        Args:
            limit: 返回数量限制
        
        Returns:
            成交记录列表
        """
        if not self.wallet_address:
            raise ValueError("需要先初始化钱包")
        
        fills = self.info.user_fills(self.wallet_address)[:limit]
        trades = []
        
        for fill in fills:
            trades.append(Trade(
                id=str(fill.get('tid', '')),
                symbol=fill.get('coin', ''),
                side=OrderSide.BUY if fill.get('side') == 'B' else OrderSide.SELL,
                price=float(fill.get('px', 0)),
                size=float(fill.get('sz', 0)),
                pnl=float(fill.get('closedPnl', 0)),
                fee=float(fill.get('fee', 0)),
                timestamp=datetime.fromtimestamp(fill.get('time', 0) / 1000),
                order_id=str(fill.get('oid', ''))
            ))
        
        return trades
    
    # ==================== 交易执行 ====================
    
    def _ensure_exchange(self):
        """确保 Exchange 客户端已初始化"""
        if self.exchange is None:
            raise ValueError("需要先初始化钱包才能执行交易")
    
    def market_order(
        self,
        symbol: str,
        is_buy: bool,
        size: float,
        slippage: float = 0.01
    ) -> Dict[str, Any]:
        """
        市价单
        
        Args:
            symbol: 交易对符号
            is_buy: 是否买入
            size: 下单数量
            slippage: 滑点容忍度
        
        Returns:
            订单结果
        """
        self._ensure_exchange()
        
        result = self.exchange.market_open(
            symbol,
            is_buy,
            size,
            None,
            slippage
        )
        
        logger.info(f"市价单执行: {symbol} {'买入' if is_buy else '卖出'} {size}, 结果: {result}")
        return result
    
    def limit_order(
        self,
        symbol: str,
        is_buy: bool,
        size: float,
        price: float,
        reduce_only: bool = False,
        post_only: bool = False
    ) -> Dict[str, Any]:
        """
        限价单
        
        Args:
            symbol: 交易对符号
            is_buy: 是否买入
            size: 下单数量
            price: 限价
            reduce_only: 是否只减仓
            post_only: 是否只做 maker
        
        Returns:
            订单结果
        """
        self._ensure_exchange()
        
        order_type = {"limit": {"tif": "Gtc"}}
        if post_only:
            order_type = {"limit": {"tif": "Alo"}}  # Add Liquidity Only
        
        result = self.exchange.order(
            symbol,
            is_buy,
            size,
            price,
            order_type,
            reduce_only=reduce_only
        )
        
        logger.info(f"限价单执行: {symbol} {'买入' if is_buy else '卖出'} {size}@{price}, 结果: {result}")
        return result
    
    def stop_order(
        self,
        symbol: str,
        is_buy: bool,
        size: float,
        trigger_price: float,
        limit_price: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        止损/止盈单
        
        Args:
            symbol: 交易对符号
            is_buy: 是否买入
            size: 下单数量
            trigger_price: 触发价格
            limit_price: 限价（可选，不提供则为市价触发）
        
        Returns:
            订单结果
        """
        self._ensure_exchange()
        
        if limit_price:
            order_type = {
                "trigger": {
                    "triggerPx": trigger_price,
                    "isMarket": False,
                    "tpsl": "sl" if not is_buy else "tp"
                }
            }
        else:
            order_type = {
                "trigger": {
                    "triggerPx": trigger_price,
                    "isMarket": True,
                    "tpsl": "sl" if not is_buy else "tp"
                }
            }
        
        result = self.exchange.order(
            symbol,
            is_buy,
            size,
            trigger_price,
            order_type,
            reduce_only=True
        )
        
        logger.info(f"止损/止盈单执行: {symbol} 触发价{trigger_price}, 结果: {result}")
        return result
    
    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """
        取消订单
        
        Args:
            symbol: 交易对符号
            order_id: 订单 ID
        
        Returns:
            取消结果
        """
        self._ensure_exchange()
        result = self.exchange.cancel(symbol, order_id)
        logger.info(f"取消订单: {symbol} {order_id}, 结果: {result}")
        return result
    
    def cancel_all_orders(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        取消所有订单
        
        Args:
            symbol: 交易对符号（可选，不提供则取消所有）
        
        Returns:
            取消结果列表
        """
        self._ensure_exchange()
        results = []
        
        orders = self.get_open_orders()
        for order in orders:
            if symbol is None or order.symbol == symbol:
                result = self.cancel_order(order.symbol, int(order.id))
                results.append(result)
        
        return results
    
    def close_position(self, symbol: str, slippage: float = 0.01) -> Optional[Dict[str, Any]]:
        """
        平仓（直接使用 market_order 实现）

        Args:
            symbol: 交易对符号
            slippage: 滑点容忍度

        Returns:
            平仓结果，如果没有持仓则返回 None
        """
        self._ensure_exchange()

        # 获取当前持仓
        positions = self.get_positions()
        position = next((p for p in positions if p.symbol == symbol), None)

        if position is None:
            logger.warning(f"平仓 {symbol}: 未找到持仓")
            return None

        logger.info(f"平仓 {symbol}: {position.side.value} {position.size}")

        # 平多仓需要卖出，平空仓需要买入
        is_buy = position.side == PositionSide.SHORT

        try:
            result = self.market_order(
                symbol=symbol,
                is_buy=is_buy,
                size=position.size,
                slippage=slippage
            )
            logger.info(f"平仓成功: {symbol}, 结果: {result}")
            return result
        except Exception as e:
            logger.error(f"平仓失败 {symbol}: {e}")
            return None
    
    def close_all_positions(self) -> List[Dict[str, Any]]:
        """
        平掉所有仓位
        
        Returns:
            平仓结果列表
        """
        self._ensure_exchange()
        results = []
        
        positions = self.get_positions()
        for position in positions:
            result = self.close_position(position.symbol)
            results.append(result)
        
        return results
    
    def close_position_limit(
        self,
        symbol: str,
        price: float,
        size: Optional[float] = None,
        post_only: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        限价平仓
        
        Args:
            symbol: 交易对符号
            price: 限价
            size: 平仓数量（可选，不提供则全部平仓）
            post_only: 是否只做 maker
        
        Returns:
            平仓结果，如果没有持仓则返回 None
        """
        self._ensure_exchange()
        
        # 获取当前持仓
        positions = self.get_positions()
        position = next((p for p in positions if p.symbol == symbol), None)
        
        if position is None:
            logger.warning(f"限价平仓 {symbol}: 未找到持仓")
            return None
        
        # 确定平仓数量
        close_size = size if size is not None else position.size
        if close_size > position.size:
            close_size = position.size
        
        logger.info(f"限价平仓 {symbol}: {position.side.value} {close_size}@{price}")
        
        # 平多仓需要卖出，平空仓需要买入
        is_buy = position.side == PositionSide.SHORT
        
        try:
            result = self.limit_order(
                symbol=symbol,
                is_buy=is_buy,
                size=close_size,
                price=price,
                reduce_only=True,
                post_only=post_only
            )
            logger.info(f"限价平仓订单已提交: {symbol}, 结果: {result}")
            return result
        except Exception as e:
            logger.error(f"限价平仓失败 {symbol}: {e}")
            return None
    
    def set_position_tp_sl(
        self,
        symbol: str,
        tp_trigger_price: Optional[float] = None,
        tp_limit_price: Optional[float] = None,
        tp_size: Optional[float] = None,
        sl_trigger_price: Optional[float] = None,
        sl_limit_price: Optional[float] = None,
        sl_size: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        设置仓位的止盈止损
        
        Args:
            symbol: 交易对符号
            tp_trigger_price: 止盈触发价格
            tp_limit_price: 止盈限价（可选，不提供则市价触发）
            tp_size: 止盈数量（可选，不提供则使用全部仓位）
            sl_trigger_price: 止损触发价格
            sl_limit_price: 止损限价（可选，不提供则市价触发）
            sl_size: 止损数量（可选，不提供则使用全部仓位）
        
        Returns:
            设置结果 {'tp': result, 'sl': result}
        """
        self._ensure_exchange()
        
        # 获取当前持仓
        positions = self.get_positions()
        position = next((p for p in positions if p.symbol == symbol), None)
        
        if position is None:
            raise ValueError(f"未找到 {symbol} 的持仓")
        
        results = {'tp': None, 'sl': None}
        
        # 设置止盈
        if tp_trigger_price is not None:
            size = tp_size if tp_size is not None else position.size
            # 平多仓需要卖出，平空仓需要买入
            is_buy = position.side == PositionSide.SHORT
            # tpsl 基于价格方向：
            # - "tp" = 价格上涨触发（多头止盈、空头止损）
            # - "sl" = 价格下跌触发（多头止损、空头止盈）
            tpsl = "tp" if position.side == PositionSide.LONG else "sl"
            
            if tp_limit_price:
                # 限价止盈
                order_type = {
                    "trigger": {
                        "triggerPx": tp_trigger_price,
                        "isMarket": False,
                        "tpsl": tpsl
                    }
                }
                result = self.exchange.order(
                    symbol,
                    is_buy,
                    size,
                    tp_limit_price,
                    order_type,
                    reduce_only=True
                )
            else:
                # 市价止盈
                order_type = {
                    "trigger": {
                        "triggerPx": tp_trigger_price,
                        "isMarket": True,
                        "tpsl": tpsl
                    }
                }
                result = self.exchange.order(
                    symbol,
                    is_buy,
                    size,
                    tp_trigger_price,
                    order_type,
                    reduce_only=True
                )
            
            results['tp'] = result
            logger.info(f"止盈设置: {symbol} 触发价{tp_trigger_price}, 限价{tp_limit_price}, tpsl={tpsl}, 结果: {result}")
        
        # 设置止损
        if sl_trigger_price is not None:
            size = sl_size if sl_size is not None else position.size
            # 平多仓需要卖出，平空仓需要买入
            is_buy = position.side == PositionSide.SHORT
            # tpsl 基于价格方向：
            # - "tp" = 价格上涨触发（多头止盈、空头止损）
            # - "sl" = 价格下跌触发（多头止损、空头止盈）
            tpsl = "sl" if position.side == PositionSide.LONG else "tp"
            
            if sl_limit_price:
                # 限价止损
                order_type = {
                    "trigger": {
                        "triggerPx": sl_trigger_price,
                        "isMarket": False,
                        "tpsl": tpsl
                    }
                }
                result = self.exchange.order(
                    symbol,
                    is_buy,
                    size,
                    sl_limit_price,
                    order_type,
                    reduce_only=True
                )
            else:
                # 市价止损
                order_type = {
                    "trigger": {
                        "triggerPx": sl_trigger_price,
                        "isMarket": True,
                        "tpsl": tpsl
                    }
                }
                result = self.exchange.order(
                    symbol,
                    is_buy,
                    size,
                    sl_trigger_price,
                    order_type,
                    reduce_only=True
                )
            
            results['sl'] = result
            logger.info(f"止损设置: {symbol} 触发价{sl_trigger_price}, 限价{sl_limit_price}, tpsl={tpsl}, 结果: {result}")
        
        return results
    
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        获取指定交易对的持仓
        
        Args:
            symbol: 交易对符号
        
        Returns:
            Position 对象，如果没有持仓则返回 None
        """
        positions = self.get_positions()
        return next((p for p in positions if p.symbol == symbol), None)
    
    def cancel_orders_by_symbol(self, symbol: str) -> List[Dict[str, Any]]:
        """
        取消指定交易对的所有订单
        
        Args:
            symbol: 交易对符号
        
        Returns:
            取消结果列表
        """
        return self.cancel_all_orders(symbol)
    
    def set_leverage(self, symbol: str, leverage: int, is_cross: bool = True) -> Dict[str, Any]:
        """
        设置杠杆
        
        Args:
            symbol: 交易对符号
            leverage: 杠杆倍数
            is_cross: 是否全仓模式
        
        Returns:
            设置结果
        """
        self._ensure_exchange()
        result = self.exchange.update_leverage(
            leverage,
            symbol,
            is_cross
        )
        logger.info(f"设置杠杆: {symbol} {leverage}x {'全仓' if is_cross else '逐仓'}, 结果: {result}")
        return result

