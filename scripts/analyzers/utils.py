"""
工具函数模块

提供重试装饰器、并发执行、检查点等工具
"""
import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    TypeVar,
    Union,
    Tuple,
)

from loguru import logger

T = TypeVar('T')


def retry_on_timeout(
    max_retries: int = 3,
    retry_delay: float = 5.0,
    timeout_keywords: Tuple[str, ...] = ('timeout', 'timed out', 'deadline exceeded'),
):
    """
    超时重试装饰器

    Args:
        max_retries: 最大重试次数
        retry_delay: 重试间隔（秒）
        timeout_keywords: 超时错误关键词

    Example:
        @retry_on_timeout(max_retries=3, retry_delay=5.0)
        def call_ai_api(prompt: str) -> str:
            return ai_client.generate(prompt)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_error: Optional[Exception] = None

            for attempt in range(1, max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()

                    # 检查是否是超时错误
                    is_timeout = any(kw in error_str for kw in timeout_keywords)

                    if is_timeout:
                        logger.warning(
                            f"{func.__name__} 超时 (尝试 {attempt}/{max_retries}): {e}"
                        )
                        if attempt < max_retries:
                            logger.info(f"等待 {retry_delay} 秒后重试...")
                            time.sleep(retry_delay)
                            continue
                    else:
                        # 非超时错误，直接抛出
                        raise

            # 所有重试都失败
            logger.error(f"{func.__name__} 重试 {max_retries} 次后仍然失败")
            raise last_error  # type: ignore

        return wrapper
    return decorator


def retry_on_timeout_async(
    max_retries: int = 3,
    retry_delay: float = 5.0,
    timeout_keywords: Tuple[str, ...] = ('timeout', 'timed out', 'deadline exceeded'),
):
    """
    异步超时重试装饰器

    用法同 retry_on_timeout，但用于 async 函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error: Optional[Exception] = None

            for attempt in range(1, max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_str = str(e).lower()

                    is_timeout = any(kw in error_str for kw in timeout_keywords)

                    if is_timeout:
                        logger.warning(
                            f"{func.__name__} 超时 (尝试 {attempt}/{max_retries}): {e}"
                        )
                        if attempt < max_retries:
                            logger.info(f"等待 {retry_delay} 秒后重试...")
                            await asyncio.sleep(retry_delay)
                            continue
                    else:
                        raise

            logger.error(f"{func.__name__} 重试 {max_retries} 次后仍然失败")
            raise last_error  # type: ignore

        return wrapper
    return decorator


def run_concurrent(
    func: Callable[[T], Any],
    items: List[T],
    max_workers: int = 5,
    desc: str = "处理中",
    show_progress: bool = True,
) -> List[Tuple[T, Any, Optional[Exception]]]:
    """
    并发执行函数

    Args:
        func: 要执行的函数
        items: 输入项列表
        max_workers: 最大并发数
        desc: 进度描述
        show_progress: 是否显示进度

    Returns:
        List of (item, result, error) tuples

    Example:
        def fetch_data(address: str) -> dict:
            return api.get_user_state(address)

        results = run_concurrent(fetch_data, addresses, max_workers=10)
        for addr, data, err in results:
            if err:
                print(f"Failed: {addr}")
            else:
                print(f"Success: {addr}, data: {data}")
    """
    results: List[Tuple[T, Any, Optional[Exception]]] = []
    total = len(items)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_item = {
            executor.submit(func, item): item
            for item in items
        }

        # 收集结果
        completed = 0
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            completed += 1

            try:
                result = future.result()
                results.append((item, result, None))
            except Exception as e:
                results.append((item, None, e))
                logger.warning(f"并发任务失败: {e}")

            if show_progress and completed % max(1, total // 10) == 0:
                logger.info(f"{desc}: {completed}/{total} ({completed/total*100:.0f}%)")

    # 按原始顺序排序
    item_order = {id(item): i for i, item in enumerate(items)}
    results.sort(key=lambda x: item_order.get(id(x[0]), 0))

    return results


async def run_concurrent_async(
    func: Callable[[T], Any],
    items: List[T],
    max_concurrent: int = 5,
    desc: str = "处理中",
) -> List[Tuple[T, Any, Optional[Exception]]]:
    """
    异步并发执行函数

    Args:
        func: 异步函数或同步函数
        items: 输入项列表
        max_concurrent: 最大并发数
        desc: 进度描述

    Returns:
        List of (item, result, error) tuples
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results: List[Tuple[T, Any, Optional[Exception]]] = []

    async def process_item(item: T) -> Tuple[T, Any, Optional[Exception]]:
        async with semaphore:
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(item)
                else:
                    # 在线程池中运行同步函数
                    loop = asyncio.get_event_loop()
                    result = await loop.run_in_executor(None, func, item)
                return (item, result, None)
            except Exception as e:
                logger.warning(f"异步任务失败: {e}")
                return (item, None, e)

    tasks = [process_item(item) for item in items]
    completed = 0
    total = len(tasks)

    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.append(result)
        completed += 1
        if completed % max(1, total // 10) == 0:
            logger.info(f"{desc}: {completed}/{total} ({completed/total*100:.0f}%)")

    # 按原始顺序排序
    item_order = {id(item): i for i, item in enumerate(items)}
    results.sort(key=lambda x: item_order.get(id(x[0]), 0))

    return results


class AnalysisCheckpoint:
    """
    分析检查点，支持断点续传

    用于长时间运行的分析任务，防止中断后丢失进度

    Example:
        checkpoint = AnalysisCheckpoint("data/.checkpoint.json")

        # 加载检查点
        state = checkpoint.load()
        if state:
            analyzed_addresses = set(state.get('analyzed', []))
        else:
            analyzed_addresses = set()

        for trader in traders:
            if trader['address'] in analyzed_addresses:
                continue  # 跳过已分析的

            # 执行分析
            result = analyze(trader)

            # 保存检查点
            analyzed_addresses.add(trader['address'])
            checkpoint.save({
                'analyzed': list(analyzed_addresses),
                'last_address': trader['address'],
                'timestamp': datetime.now().isoformat()
            })

        # 完成后清除检查点
        checkpoint.clear()
    """

    def __init__(self, checkpoint_file: Union[str, Path] = "data/.analysis_checkpoint.json"):
        self.checkpoint_file = Path(checkpoint_file)

    def save(self, state: Dict[str, Any]) -> None:
        """
        保存检查点

        Args:
            state: 状态数据
        """
        # 确保目录存在
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

        # 添加元数据
        state['_checkpoint_time'] = datetime.now().isoformat()
        state['_version'] = 1

        with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, ensure_ascii=False, default=str)

        logger.debug(f"检查点已保存: {self.checkpoint_file}")

    def load(self) -> Optional[Dict[str, Any]]:
        """
        加载检查点

        Returns:
            检查点数据，如果不存在返回 None
        """
        if not self.checkpoint_file.exists():
            return None

        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                state = json.load(f)

            logger.info(f"已加载检查点: {self.checkpoint_file}")
            if '_checkpoint_time' in state:
                logger.info(f"  检查点时间: {state['_checkpoint_time']}")

            return state
        except Exception as e:
            logger.warning(f"加载检查点失败: {e}")
            return None

    def clear(self) -> None:
        """清除检查点"""
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()
            logger.info(f"检查点已清除: {self.checkpoint_file}")

    def exists(self) -> bool:
        """检查点是否存在"""
        return self.checkpoint_file.exists()


class RateLimiter:
    """
    速率限制器

    控制 API 调用频率

    Example:
        limiter = RateLimiter(calls_per_second=2)

        for item in items:
            limiter.wait()  # 等待直到可以调用
            result = api.call(item)
    """

    def __init__(self, calls_per_second: float = 1.0, burst: int = 1):
        """
        初始化速率限制器

        Args:
            calls_per_second: 每秒允许的调用次数
            burst: 突发允许的调用次数
        """
        self.min_interval = 1.0 / calls_per_second
        self.burst = burst
        self.tokens = burst
        self.last_time = time.monotonic()
        self._lock = asyncio.Lock() if asyncio.get_event_loop().is_running() else None

    def wait(self) -> None:
        """同步等待"""
        now = time.monotonic()
        elapsed = now - self.last_time

        # 补充 tokens
        self.tokens = min(self.burst, self.tokens + elapsed / self.min_interval)
        self.last_time = now

        if self.tokens < 1:
            sleep_time = (1 - self.tokens) * self.min_interval
            time.sleep(sleep_time)
            self.tokens = 0
            self.last_time = time.monotonic()
        else:
            self.tokens -= 1

    async def wait_async(self) -> None:
        """异步等待"""
        async with self._lock:  # type: ignore
            now = time.monotonic()
            elapsed = now - self.last_time

            self.tokens = min(self.burst, self.tokens + elapsed / self.min_interval)
            self.last_time = now

            if self.tokens < 1:
                sleep_time = (1 - self.tokens) * self.min_interval
                await asyncio.sleep(sleep_time)
                self.tokens = 0
                self.last_time = time.monotonic()
            else:
                self.tokens -= 1


def format_duration(seconds: float) -> str:
    """格式化时长"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = seconds % 60
        return f"{minutes}m {secs:.0f}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def format_number(value: float, precision: int = 2) -> str:
    """格式化数字（带千位分隔符）"""
    if abs(value) >= 1_000_000:
        return f"${value/1_000_000:.{precision}f}M"
    elif abs(value) >= 1_000:
        return f"${value/1_000:.{precision}f}K"
    else:
        return f"${value:,.{precision}f}"


def format_percent(value: float, precision: int = 1) -> str:
    """格式化百分比"""
    return f"{value * 100:.{precision}f}%"


def safe_get(data: Dict, *keys: str, default: Any = None) -> Any:
    """
    安全获取嵌套字典值

    Example:
        data = {'a': {'b': {'c': 1}}}
        value = safe_get(data, 'a', 'b', 'c')  # 1
        value = safe_get(data, 'a', 'x', default=0)  # 0
    """
    result = data
    for key in keys:
        if isinstance(result, dict):
            result = result.get(key, default)
        else:
            return default
    return result
