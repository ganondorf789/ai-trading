"""
跟单记录工具函数
提供创建 tracking_data 的公共方法，供多个模块复用
"""
from typing import Dict, Optional, Any


def build_tracking_data(
    target_address: str,
    target_name: str,
    symbol: str,
    config: Dict[str, Any],
    target_position: Optional[Dict[str, Any]] = None,
    target_is_starred: bool = False,
    target_score: Optional[float] = None,
    target_rating: Optional[str] = None,
    status: str = 'pending'
) -> Dict[str, Any]:
    """
    构建跟单记录数据
    
    Args:
        target_address: 目标交易员地址
        target_name: 目标交易员名称
        symbol: 币种符号
        config: 配置数据，包含跟单参数和自动补仓配置
            - copy_ratio: 跟单比例
            - max_position_size_usd: 最大仓位（USD）
            - min_position_size_usd: 最小仓位（USD）
            - copy_leverage: 是否复制杠杆
            - max_leverage: 最大杠杆
            - default_leverage: 默认杠杆
            - slippage: 滑点
            - auto_replenish: 是否启用自动补仓
            - replenish_ratio: 补仓比例
            - replenish_min_value_usd: 单次补仓最小金额
            - replenish_max_value_usd: 单次补仓最大金额
        target_position: 目标仓位快照信息（可选）
            - size: 仓位大小
            - side: 仓位方向 ('long' / 'short')
            - entry_price: 入场价格
            - leverage: 杠杆倍数
        target_is_starred: 目标交易员是否被标记
        target_score: 目标交易员评分
        target_rating: 目标交易员评级
        status: 初始状态（默认 'pending'）
    
    Returns:
        跟单记录数据字典
    """
    tracking_data = {
        'target_address': target_address,
        'target_name': target_name or target_address[:10] + '...',
        'symbol': symbol,
        'is_enabled': True,
        # 跟单参数
        'copy_ratio': config.get('copy_ratio', 0.1),
        'max_position_size_usd': config.get('max_position_size_usd', 500.0),
        'min_position_size_usd': config.get('min_position_size_usd', 20.0),
        'copy_leverage': config.get('copy_leverage', False),
        'max_leverage': config.get('max_leverage', 10),
        'default_leverage': config.get('default_leverage', 3),
        'slippage': config.get('slippage', 0.001),
        # 自动补仓配置
        'auto_replenish': config.get('auto_replenish', False),
        'replenish_ratio': config.get('replenish_ratio', 0.5),
        'replenish_min_value_usd': config.get('replenish_min_value_usd', 10.0),
        'replenish_max_value_usd': config.get('replenish_max_value_usd', 100.0),
        # 状态
        'target_is_starred': target_is_starred,
        'target_score': target_score,
        'target_rating': target_rating,
        'status': status,
        # 仓位模式
        'position_mode': config.get('position_mode', 'cross'),
        # 止盈止损
        'take_profit_enabled': config.get('take_profit_enabled', False),
        'take_profit_percent': config.get('take_profit_percent', 50),
        'stop_loss_enabled': config.get('stop_loss_enabled', False),
        'stop_loss_percent': config.get('stop_loss_percent', 20),
    }
    
    # 如果提供了目标仓位信息，添加快照
    if target_position:
        size = target_position.get('size', 0)
        tracking_data['target_initial_size'] = abs(size) if size else target_position.get('szi', 0)
        tracking_data['target_initial_side'] = target_position.get('side') or ('long' if size > 0 else 'short')
        tracking_data['target_initial_entry_price'] = target_position.get('entry_price') or target_position.get('entry_px', 0)
        tracking_data['target_initial_leverage'] = target_position.get('leverage', 1)
    
    return tracking_data


def build_tracking_data_from_dataclass(
    config_obj: Any,
    target_address: str,
    symbol: str,
    target_position: Dict[str, Any],
    target_is_starred: bool = False,
    target_score: Optional[float] = None,
    target_rating: Optional[str] = None,
    status: str = 'pending'
) -> Dict[str, Any]:
    """
    从 dataclass 配置对象构建跟单记录数据
    
    Args:
        config_obj: AddressConfig 或类似的 dataclass 配置对象
        target_address: 目标交易员地址
        symbol: 币种符号
        target_position: 目标仓位信息
        target_is_starred: 目标交易员是否被标记
        target_score: 目标交易员评分
        target_rating: 目标交易员评级
        status: 初始状态
    
    Returns:
        跟单记录数据字典
    """
    # 从 dataclass 获取配置
    config = {
        'copy_ratio': getattr(config_obj, 'copy_ratio', 0.1),
        'max_position_size_usd': getattr(config_obj, 'max_position_size_usd', 500.0),
        'min_position_size_usd': getattr(config_obj, 'min_position_size_usd', 20.0),
        'copy_leverage': getattr(config_obj, 'copy_leverage', False),
        'max_leverage': getattr(config_obj, 'max_leverage', 10),
        'default_leverage': getattr(config_obj, 'default_leverage', 3),
        'slippage': getattr(config_obj, 'slippage', 0.001),
        'auto_replenish': getattr(config_obj, 'auto_replenish', False),
        'replenish_ratio': getattr(config_obj, 'replenish_ratio', 0.5),
        'replenish_min_value_usd': getattr(config_obj, 'replenish_min_value_usd', 10.0),
        'replenish_max_value_usd': getattr(config_obj, 'replenish_max_value_usd', 100.0),
        'position_mode': getattr(config_obj, 'position_mode', 'cross'),
        'take_profit_enabled': getattr(config_obj, 'take_profit_enabled', False),
        'take_profit_percent': getattr(config_obj, 'take_profit_percent', 50),
        'stop_loss_enabled': getattr(config_obj, 'stop_loss_enabled', False),
        'stop_loss_percent': getattr(config_obj, 'stop_loss_percent', 20),
    }
    
    target_name = getattr(config_obj, 'name', '') or target_address[:10] + '...'
    
    return build_tracking_data(
        target_address=target_address,
        target_name=target_name,
        symbol=symbol,
        config=config,
        target_position=target_position,
        target_is_starred=target_is_starred,
        target_score=target_score,
        target_rating=target_rating,
        status=status
    )
