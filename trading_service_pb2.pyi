from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from collections.abc import Iterable as _Iterable, Mapping as _Mapping
from typing import ClassVar as _ClassVar, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class GetPositionTrackingRequest(_message.Message):
    __slots__ = ("tracking_id",)
    TRACKING_ID_FIELD_NUMBER: _ClassVar[int]
    tracking_id: int
    def __init__(self, tracking_id: _Optional[int] = ...) -> None: ...

class GetActivePositionTrackingsRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class SavePositionTrackingRequest(_message.Message):
    __slots__ = ("id", "target_address", "symbol", "target_side", "copy_ratio", "max_position_size", "slippage", "is_enabled", "status", "my_size", "my_side", "my_entry_price", "user_id", "address_id", "target_entry_price", "target_size", "nickname", "auto_replenish", "replenish_ratio", "replenish_min_value_usd", "replenish_max_value_usd", "target_name", "min_position_size", "copy_leverage", "max_leverage", "default_leverage", "target_initial_size", "target_initial_side", "target_initial_entry_price", "target_initial_leverage", "started_at", "closed_at", "target_is_starred", "target_score", "target_rating")
    ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    TARGET_SIDE_FIELD_NUMBER: _ClassVar[int]
    COPY_RATIO_FIELD_NUMBER: _ClassVar[int]
    MAX_POSITION_SIZE_FIELD_NUMBER: _ClassVar[int]
    SLIPPAGE_FIELD_NUMBER: _ClassVar[int]
    IS_ENABLED_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    MY_SIZE_FIELD_NUMBER: _ClassVar[int]
    MY_SIDE_FIELD_NUMBER: _ClassVar[int]
    MY_ENTRY_PRICE_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ENTRY_PRICE_FIELD_NUMBER: _ClassVar[int]
    TARGET_SIZE_FIELD_NUMBER: _ClassVar[int]
    NICKNAME_FIELD_NUMBER: _ClassVar[int]
    AUTO_REPLENISH_FIELD_NUMBER: _ClassVar[int]
    REPLENISH_RATIO_FIELD_NUMBER: _ClassVar[int]
    REPLENISH_MIN_VALUE_USD_FIELD_NUMBER: _ClassVar[int]
    REPLENISH_MAX_VALUE_USD_FIELD_NUMBER: _ClassVar[int]
    TARGET_NAME_FIELD_NUMBER: _ClassVar[int]
    MIN_POSITION_SIZE_FIELD_NUMBER: _ClassVar[int]
    COPY_LEVERAGE_FIELD_NUMBER: _ClassVar[int]
    MAX_LEVERAGE_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_LEVERAGE_FIELD_NUMBER: _ClassVar[int]
    TARGET_INITIAL_SIZE_FIELD_NUMBER: _ClassVar[int]
    TARGET_INITIAL_SIDE_FIELD_NUMBER: _ClassVar[int]
    TARGET_INITIAL_ENTRY_PRICE_FIELD_NUMBER: _ClassVar[int]
    TARGET_INITIAL_LEVERAGE_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    CLOSED_AT_FIELD_NUMBER: _ClassVar[int]
    TARGET_IS_STARRED_FIELD_NUMBER: _ClassVar[int]
    TARGET_SCORE_FIELD_NUMBER: _ClassVar[int]
    TARGET_RATING_FIELD_NUMBER: _ClassVar[int]
    id: int
    target_address: str
    symbol: str
    target_side: str
    copy_ratio: float
    max_position_size: float
    slippage: float
    is_enabled: bool
    status: str
    my_size: float
    my_side: str
    my_entry_price: float
    user_id: int
    address_id: int
    target_entry_price: float
    target_size: float
    nickname: str
    auto_replenish: bool
    replenish_ratio: float
    replenish_min_value_usd: float
    replenish_max_value_usd: float
    target_name: str
    min_position_size: float
    copy_leverage: bool
    max_leverage: int
    default_leverage: int
    target_initial_size: float
    target_initial_side: str
    target_initial_entry_price: float
    target_initial_leverage: int
    started_at: str
    closed_at: str
    target_is_starred: bool
    target_score: float
    target_rating: str
    def __init__(self, id: _Optional[int] = ..., target_address: _Optional[str] = ..., symbol: _Optional[str] = ..., target_side: _Optional[str] = ..., copy_ratio: _Optional[float] = ..., max_position_size: _Optional[float] = ..., slippage: _Optional[float] = ..., is_enabled: bool = ..., status: _Optional[str] = ..., my_size: _Optional[float] = ..., my_side: _Optional[str] = ..., my_entry_price: _Optional[float] = ..., user_id: _Optional[int] = ..., address_id: _Optional[int] = ..., target_entry_price: _Optional[float] = ..., target_size: _Optional[float] = ..., nickname: _Optional[str] = ..., auto_replenish: bool = ..., replenish_ratio: _Optional[float] = ..., replenish_min_value_usd: _Optional[float] = ..., replenish_max_value_usd: _Optional[float] = ..., target_name: _Optional[str] = ..., min_position_size: _Optional[float] = ..., copy_leverage: bool = ..., max_leverage: _Optional[int] = ..., default_leverage: _Optional[int] = ..., target_initial_size: _Optional[float] = ..., target_initial_side: _Optional[str] = ..., target_initial_entry_price: _Optional[float] = ..., target_initial_leverage: _Optional[int] = ..., started_at: _Optional[str] = ..., closed_at: _Optional[str] = ..., target_is_starred: bool = ..., target_score: _Optional[float] = ..., target_rating: _Optional[str] = ...) -> None: ...

class PositionTrackingResponse(_message.Message):
    __slots__ = ("success", "tracking", "error")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    TRACKING_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    success: bool
    tracking: PositionTracking
    error: str
    def __init__(self, success: bool = ..., tracking: _Optional[_Union[PositionTracking, _Mapping]] = ..., error: _Optional[str] = ...) -> None: ...

class PositionTrackingListResponse(_message.Message):
    __slots__ = ("success", "trackings", "error")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    TRACKINGS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    success: bool
    trackings: _containers.RepeatedCompositeFieldContainer[PositionTracking]
    error: str
    def __init__(self, success: bool = ..., trackings: _Optional[_Iterable[_Union[PositionTracking, _Mapping]]] = ..., error: _Optional[str] = ...) -> None: ...

class PositionTracking(_message.Message):
    __slots__ = ("id", "target_address", "symbol", "target_side", "copy_ratio", "max_position_size", "slippage", "is_enabled", "status", "my_size", "my_side", "my_entry_price", "user_id", "address_id", "target_entry_price", "target_size", "nickname", "created_at", "updated_at", "close_reason", "closed_pnl", "auto_replenish", "replenish_ratio", "replenish_min_value_usd", "replenish_max_value_usd", "target_name", "min_position_size", "copy_leverage", "max_leverage", "default_leverage", "target_initial_size", "target_initial_side", "target_initial_entry_price", "target_initial_leverage", "started_at", "closed_at", "target_is_starred", "target_score", "target_rating")
    ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    TARGET_SIDE_FIELD_NUMBER: _ClassVar[int]
    COPY_RATIO_FIELD_NUMBER: _ClassVar[int]
    MAX_POSITION_SIZE_FIELD_NUMBER: _ClassVar[int]
    SLIPPAGE_FIELD_NUMBER: _ClassVar[int]
    IS_ENABLED_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    MY_SIZE_FIELD_NUMBER: _ClassVar[int]
    MY_SIDE_FIELD_NUMBER: _ClassVar[int]
    MY_ENTRY_PRICE_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_ID_FIELD_NUMBER: _ClassVar[int]
    TARGET_ENTRY_PRICE_FIELD_NUMBER: _ClassVar[int]
    TARGET_SIZE_FIELD_NUMBER: _ClassVar[int]
    NICKNAME_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    CLOSE_REASON_FIELD_NUMBER: _ClassVar[int]
    CLOSED_PNL_FIELD_NUMBER: _ClassVar[int]
    AUTO_REPLENISH_FIELD_NUMBER: _ClassVar[int]
    REPLENISH_RATIO_FIELD_NUMBER: _ClassVar[int]
    REPLENISH_MIN_VALUE_USD_FIELD_NUMBER: _ClassVar[int]
    REPLENISH_MAX_VALUE_USD_FIELD_NUMBER: _ClassVar[int]
    TARGET_NAME_FIELD_NUMBER: _ClassVar[int]
    MIN_POSITION_SIZE_FIELD_NUMBER: _ClassVar[int]
    COPY_LEVERAGE_FIELD_NUMBER: _ClassVar[int]
    MAX_LEVERAGE_FIELD_NUMBER: _ClassVar[int]
    DEFAULT_LEVERAGE_FIELD_NUMBER: _ClassVar[int]
    TARGET_INITIAL_SIZE_FIELD_NUMBER: _ClassVar[int]
    TARGET_INITIAL_SIDE_FIELD_NUMBER: _ClassVar[int]
    TARGET_INITIAL_ENTRY_PRICE_FIELD_NUMBER: _ClassVar[int]
    TARGET_INITIAL_LEVERAGE_FIELD_NUMBER: _ClassVar[int]
    STARTED_AT_FIELD_NUMBER: _ClassVar[int]
    CLOSED_AT_FIELD_NUMBER: _ClassVar[int]
    TARGET_IS_STARRED_FIELD_NUMBER: _ClassVar[int]
    TARGET_SCORE_FIELD_NUMBER: _ClassVar[int]
    TARGET_RATING_FIELD_NUMBER: _ClassVar[int]
    id: int
    target_address: str
    symbol: str
    target_side: str
    copy_ratio: float
    max_position_size: float
    slippage: float
    is_enabled: bool
    status: str
    my_size: float
    my_side: str
    my_entry_price: float
    user_id: int
    address_id: int
    target_entry_price: float
    target_size: float
    nickname: str
    created_at: str
    updated_at: str
    close_reason: str
    closed_pnl: float
    auto_replenish: bool
    replenish_ratio: float
    replenish_min_value_usd: float
    replenish_max_value_usd: float
    target_name: str
    min_position_size: float
    copy_leverage: bool
    max_leverage: int
    default_leverage: int
    target_initial_size: float
    target_initial_side: str
    target_initial_entry_price: float
    target_initial_leverage: int
    started_at: str
    closed_at: str
    target_is_starred: bool
    target_score: float
    target_rating: str
    def __init__(self, id: _Optional[int] = ..., target_address: _Optional[str] = ..., symbol: _Optional[str] = ..., target_side: _Optional[str] = ..., copy_ratio: _Optional[float] = ..., max_position_size: _Optional[float] = ..., slippage: _Optional[float] = ..., is_enabled: bool = ..., status: _Optional[str] = ..., my_size: _Optional[float] = ..., my_side: _Optional[str] = ..., my_entry_price: _Optional[float] = ..., user_id: _Optional[int] = ..., address_id: _Optional[int] = ..., target_entry_price: _Optional[float] = ..., target_size: _Optional[float] = ..., nickname: _Optional[str] = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ..., close_reason: _Optional[str] = ..., closed_pnl: _Optional[float] = ..., auto_replenish: bool = ..., replenish_ratio: _Optional[float] = ..., replenish_min_value_usd: _Optional[float] = ..., replenish_max_value_usd: _Optional[float] = ..., target_name: _Optional[str] = ..., min_position_size: _Optional[float] = ..., copy_leverage: bool = ..., max_leverage: _Optional[int] = ..., default_leverage: _Optional[int] = ..., target_initial_size: _Optional[float] = ..., target_initial_side: _Optional[str] = ..., target_initial_entry_price: _Optional[float] = ..., target_initial_leverage: _Optional[int] = ..., started_at: _Optional[str] = ..., closed_at: _Optional[str] = ..., target_is_starred: bool = ..., target_score: _Optional[float] = ..., target_rating: _Optional[str] = ...) -> None: ...

class SavePositionTrackingResponse(_message.Message):
    __slots__ = ("success", "tracking_id", "error")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    TRACKING_ID_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    success: bool
    tracking_id: int
    error: str
    def __init__(self, success: bool = ..., tracking_id: _Optional[int] = ..., error: _Optional[str] = ...) -> None: ...

class UpdateTrackingStatusRequest(_message.Message):
    __slots__ = ("tracking_id", "status", "close_reason", "closed_pnl")
    TRACKING_ID_FIELD_NUMBER: _ClassVar[int]
    STATUS_FIELD_NUMBER: _ClassVar[int]
    CLOSE_REASON_FIELD_NUMBER: _ClassVar[int]
    CLOSED_PNL_FIELD_NUMBER: _ClassVar[int]
    tracking_id: int
    status: str
    close_reason: str
    closed_pnl: float
    def __init__(self, tracking_id: _Optional[int] = ..., status: _Optional[str] = ..., close_reason: _Optional[str] = ..., closed_pnl: _Optional[float] = ...) -> None: ...

class UpdateTrackingPositionRequest(_message.Message):
    __slots__ = ("tracking_id", "my_size", "my_side", "my_entry_price")
    TRACKING_ID_FIELD_NUMBER: _ClassVar[int]
    MY_SIZE_FIELD_NUMBER: _ClassVar[int]
    MY_SIDE_FIELD_NUMBER: _ClassVar[int]
    MY_ENTRY_PRICE_FIELD_NUMBER: _ClassVar[int]
    tracking_id: int
    my_size: float
    my_side: str
    my_entry_price: float
    def __init__(self, tracking_id: _Optional[int] = ..., my_size: _Optional[float] = ..., my_side: _Optional[str] = ..., my_entry_price: _Optional[float] = ...) -> None: ...

class UpdateTrackingResponse(_message.Message):
    __slots__ = ("success", "error")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    success: bool
    error: str
    def __init__(self, success: bool = ..., error: _Optional[str] = ...) -> None: ...

class GetEnabledCopyAddressesRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: int
    def __init__(self, user_id: _Optional[int] = ...) -> None: ...

class CopyAddressListResponse(_message.Message):
    __slots__ = ("success", "addresses", "error")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ADDRESSES_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    success: bool
    addresses: _containers.RepeatedCompositeFieldContainer[CopyAddress]
    error: str
    def __init__(self, success: bool = ..., addresses: _Optional[_Iterable[_Union[CopyAddress, _Mapping]]] = ..., error: _Optional[str] = ...) -> None: ...

class CopyAddress(_message.Message):
    __slots__ = ("id", "user_id", "address", "nickname", "copy_ratio", "max_position_size", "slippage", "is_enabled", "auto_copy", "whitelist_symbols", "blacklist_symbols", "created_at", "updated_at")
    ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ADDRESS_FIELD_NUMBER: _ClassVar[int]
    NICKNAME_FIELD_NUMBER: _ClassVar[int]
    COPY_RATIO_FIELD_NUMBER: _ClassVar[int]
    MAX_POSITION_SIZE_FIELD_NUMBER: _ClassVar[int]
    SLIPPAGE_FIELD_NUMBER: _ClassVar[int]
    IS_ENABLED_FIELD_NUMBER: _ClassVar[int]
    AUTO_COPY_FIELD_NUMBER: _ClassVar[int]
    WHITELIST_SYMBOLS_FIELD_NUMBER: _ClassVar[int]
    BLACKLIST_SYMBOLS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    id: int
    user_id: int
    address: str
    nickname: str
    copy_ratio: float
    max_position_size: float
    slippage: float
    is_enabled: bool
    auto_copy: bool
    whitelist_symbols: str
    blacklist_symbols: str
    created_at: str
    updated_at: str
    def __init__(self, id: _Optional[int] = ..., user_id: _Optional[int] = ..., address: _Optional[str] = ..., nickname: _Optional[str] = ..., copy_ratio: _Optional[float] = ..., max_position_size: _Optional[float] = ..., slippage: _Optional[float] = ..., is_enabled: bool = ..., auto_copy: bool = ..., whitelist_symbols: _Optional[str] = ..., blacklist_symbols: _Optional[str] = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ...) -> None: ...

class CheckPositionTrackingExistsRequest(_message.Message):
    __slots__ = ("target_address", "symbol")
    TARGET_ADDRESS_FIELD_NUMBER: _ClassVar[int]
    SYMBOL_FIELD_NUMBER: _ClassVar[int]
    target_address: str
    symbol: str
    def __init__(self, target_address: _Optional[str] = ..., symbol: _Optional[str] = ...) -> None: ...

class CheckPositionTrackingExistsResponse(_message.Message):
    __slots__ = ("exists", "error")
    EXISTS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    exists: bool
    error: str
    def __init__(self, exists: bool = ..., error: _Optional[str] = ...) -> None: ...

class PublishRequest(_message.Message):
    __slots__ = ("channel", "message")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    channel: str
    message: str
    def __init__(self, channel: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class PublishResponse(_message.Message):
    __slots__ = ("success", "receivers", "error")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    RECEIVERS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    success: bool
    receivers: int
    error: str
    def __init__(self, success: bool = ..., receivers: _Optional[int] = ..., error: _Optional[str] = ...) -> None: ...

class SubscribeRequest(_message.Message):
    __slots__ = ("channels",)
    CHANNELS_FIELD_NUMBER: _ClassVar[int]
    channels: _containers.RepeatedScalarFieldContainer[str]
    def __init__(self, channels: _Optional[_Iterable[str]] = ...) -> None: ...

class SubscribeMessage(_message.Message):
    __slots__ = ("channel", "message")
    CHANNEL_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    channel: str
    message: str
    def __init__(self, channel: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class SetExRequest(_message.Message):
    __slots__ = ("key", "value", "expire_seconds")
    KEY_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    EXPIRE_SECONDS_FIELD_NUMBER: _ClassVar[int]
    key: str
    value: str
    expire_seconds: int
    def __init__(self, key: _Optional[str] = ..., value: _Optional[str] = ..., expire_seconds: _Optional[int] = ...) -> None: ...

class SetExResponse(_message.Message):
    __slots__ = ("success", "error")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    success: bool
    error: str
    def __init__(self, success: bool = ..., error: _Optional[str] = ...) -> None: ...

class GetRequest(_message.Message):
    __slots__ = ("key",)
    KEY_FIELD_NUMBER: _ClassVar[int]
    key: str
    def __init__(self, key: _Optional[str] = ...) -> None: ...

class GetResponse(_message.Message):
    __slots__ = ("success", "value", "error")
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    VALUE_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    success: bool
    value: str
    error: str
    def __init__(self, success: bool = ..., value: _Optional[str] = ..., error: _Optional[str] = ...) -> None: ...
