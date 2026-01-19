"""
测试 Hyperliquid 获取仓位的频率限制
测试不同的请求频率（如每秒3个地址）
使用异步实现
"""
import argparse
import asyncio
import time
import statistics
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

import aiohttp
from loguru import logger
from hyperliquid.utils import constants

# 测试地址列表
TEST_ADDRESSES = [
    "0xec326a384ae965647d87e1f85db46d2efa15ae82",
    "0x90924bd2a82c481170e98051196a5bde02d82b15",
    "0xa8ef95dbd3db55911d3307930a84b27d6e969526",
    "0x162cc7c861ebd0c06b3d72319201150482518185",
    "0x399965e15d4e61ec3529cc98b7f7ebb93b733336",
    "0x50b309f78e774a756a2230e1769729094cac9f20",
    "0xff4cd3826ecee12acd4329aada4a2d3419fc463c",
    "0x7839e2f2c375dd2935193f2736167514efff9916",
    "0xecb63caa47c7c4e77f60f1ce858cf28dc2b82b00",
    "0xdf9ea6ec3b7109935ccb4fb267e15ac1fb077ab1",
    "0x7b7f72a28fe109fa703eeed7984f2a8a68fedee2",
    "0x023a3d058020fb76cca98f01b3c48c8938a22355",
    "0xad8be12a452b5b8f9ad9883f6e8e67536627db4b",
    "0x53babe76166eae33c861aeddf9ce89af20311cd0",
]


@dataclass
class RequestResult:
    """单次请求结果"""
    address: str
    success: bool
    duration_ms: float
    error: str = ""
    positions_count: int = 0


@dataclass
class TestResult:
    """测试结果汇总"""
    test_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration_ms: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    requests_per_second: float
    errors: List[str]


class AsyncRateLimiter:
    """异步速率限制器 - 令牌桶算法"""
    
    def __init__(self, rate: float, max_tokens: Optional[int] = None):
        """
        Args:
            rate: 每秒允许的请求数
            max_tokens: 最大令牌数（突发容量），默认等于rate
        """
        self.rate = rate
        self.max_tokens = max_tokens or int(rate)
        self.tokens = self.max_tokens
        self.last_update = time.perf_counter()
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        """获取一个令牌，如果没有可用令牌则等待"""
        async with self._lock:
            now = time.perf_counter()
            # 补充令牌
            elapsed = now - self.last_update
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens < 1:
                # 需要等待
                wait_time = (1 - self.tokens) / self.rate
                await asyncio.sleep(wait_time)
                self.tokens = 0
                self.last_update = time.perf_counter()
            else:
                self.tokens -= 1


class RateLimitTester:
    """频率限制测试器（异步版本）"""
    
    def __init__(self, api_url: str = constants.MAINNET_API_URL):
        self.api_url = api_url
        self.info_url = f"{api_url}/info"
        
    async def fetch_user_state_async(self, session: aiohttp.ClientSession, 
                                     address: str) -> RequestResult:
        """异步获取单个用户状态"""
        start_time = time.perf_counter()
        try:
            payload = {
                "type": "clearinghouseState",
                "user": address
            }
            async with session.post(self.info_url, json=payload) as response:
                state = await response.json()
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                # 统计仓位数量
                positions_count = len([
                    p for p in state.get('assetPositions', [])
                    if float(p.get('position', {}).get('szi', 0)) != 0
                ])
                
                return RequestResult(
                    address=address,
                    success=True,
                    duration_ms=duration_ms,
                    positions_count=positions_count
                )
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return RequestResult(
                address=address,
                success=False,
                duration_ms=duration_ms,
                error=str(e)
            )
    
    async def test_rate_limited_async(self, addresses: List[str], 
                                       requests_per_second: float = 3) -> TestResult:
        """
        异步限速请求测试 - 使用令牌桶算法控制每秒请求数
        
        Args:
            addresses: 地址列表
            requests_per_second: 每秒请求数（默认3）
        """
        logger.info(f"开始异步限速请求测试，地址数: {len(addresses)}，"
                   f"目标速率: {requests_per_second} 请求/秒")
        
        rate_limiter = AsyncRateLimiter(rate=requests_per_second)
        results: List[RequestResult] = []
        start_time = time.perf_counter()
        
        async with aiohttp.ClientSession() as session:
            async def fetch_with_rate_limit(idx: int, address: str):
                await rate_limiter.acquire()
                result = await self.fetch_user_state_async(session, address)
                status = "✓" if result.success else "✗"
                logger.info(f"  [{idx+1}/{len(addresses)}] {status} {address[:10]}... "
                           f"耗时: {result.duration_ms:.1f}ms, 仓位数: {result.positions_count}")
                return result
            
            # 创建所有任务
            tasks = [
                fetch_with_rate_limit(i, addr) 
                for i, addr in enumerate(addresses)
            ]
            
            # 并发执行，但受速率限制
            results = await asyncio.gather(*tasks)
        
        total_duration_ms = (time.perf_counter() - start_time) * 1000
        return self._summarize_results(
            f"异步限速请求({requests_per_second}/s)", 
            list(results), total_duration_ms
        )
    
    async def test_concurrent_async(self, addresses: List[str], 
                                     max_concurrent: int = 10) -> TestResult:
        """
        异步并发请求测试
        
        Args:
            addresses: 地址列表
            max_concurrent: 最大并发数
        """
        logger.info(f"开始异步并发请求测试，地址数: {len(addresses)}，并发数: {max_concurrent}")
        
        results: List[RequestResult] = []
        start_time = time.perf_counter()
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async with aiohttp.ClientSession() as session:
            async def fetch_with_semaphore(idx: int, address: str):
                async with semaphore:
                    result = await self.fetch_user_state_async(session, address)
                    status = "✓" if result.success else "✗"
                    logger.info(f"  [{idx+1}/{len(addresses)}] {status} {address[:10]}... "
                               f"耗时: {result.duration_ms:.1f}ms, 仓位数: {result.positions_count}")
                    return result
            
            tasks = [
                fetch_with_semaphore(i, addr) 
                for i, addr in enumerate(addresses)
            ]
            results = await asyncio.gather(*tasks)
        
        total_duration_ms = (time.perf_counter() - start_time) * 1000
        return self._summarize_results(
            f"异步并发请求(concurrent={max_concurrent})", 
            list(results), total_duration_ms
        )
    
    async def test_burst_async(self, addresses: List[str], burst_size: int = 3, 
                                delay_between_bursts_ms: float = 1000) -> TestResult:
        """
        异步突发请求测试 - 每次发送一批请求，然后等待
        
        Args:
            addresses: 地址列表
            burst_size: 每批请求数量（默认3，即每秒3个）
            delay_between_bursts_ms: 批次间隔（毫秒）
        """
        logger.info(f"开始异步突发请求测试，地址数: {len(addresses)}，"
                   f"批大小: {burst_size}，批间隔: {delay_between_bursts_ms}ms")
        
        results: List[RequestResult] = []
        start_time = time.perf_counter()
        completed = 0
        
        async with aiohttp.ClientSession() as session:
            # 分批处理
            for batch_idx in range(0, len(addresses), burst_size):
                batch = addresses[batch_idx:batch_idx + burst_size]
                batch_num = batch_idx // burst_size + 1
                logger.info(f"  批次 {batch_num}: 发送 {len(batch)} 个请求...")
                
                # 并发发送这一批
                tasks = [
                    self.fetch_user_state_async(session, addr) 
                    for addr in batch
                ]
                batch_results = await asyncio.gather(*tasks)
                
                for result in batch_results:
                    completed += 1
                    results.append(result)
                    status = "✓" if result.success else "✗"
                    error_info = f" 错误: {result.error}" if result.error else ""
                    logger.info(f"    [{completed}/{len(addresses)}] {status} {result.address[:10]}... "
                               f"耗时: {result.duration_ms:.1f}ms{error_info}")
                
                # 如果还有下一批，等待
                if batch_idx + burst_size < len(addresses):
                    logger.info(f"  等待 {delay_between_bursts_ms}ms...")
                    await asyncio.sleep(delay_between_bursts_ms / 1000)
        
        total_duration_ms = (time.perf_counter() - start_time) * 1000
        return self._summarize_results(
            f"异步突发请求(burst={burst_size}, interval={delay_between_bursts_ms}ms)", 
            results, total_duration_ms
        )
    
    def _summarize_results(self, test_name: str, results: List[RequestResult], 
                          total_duration_ms: float) -> TestResult:
        """汇总测试结果"""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        latencies = [r.duration_ms for r in results]
        
        return TestResult(
            test_name=test_name,
            total_requests=len(results),
            successful_requests=len(successful),
            failed_requests=len(failed),
            total_duration_ms=total_duration_ms,
            avg_latency_ms=statistics.mean(latencies) if latencies else 0,
            min_latency_ms=min(latencies) if latencies else 0,
            max_latency_ms=max(latencies) if latencies else 0,
            requests_per_second=len(results) / (total_duration_ms / 1000) if total_duration_ms > 0 else 0,
            errors=list(set(r.error for r in failed if r.error))
        )
    
    def print_result(self, result: TestResult):
        """打印测试结果"""
        print("\n" + "=" * 60)
        print(f"测试: {result.test_name}")
        print("=" * 60)
        print(f"总请求数:     {result.total_requests}")
        print(f"成功:         {result.successful_requests}")
        print(f"失败:         {result.failed_requests}")
        print(f"成功率:       {result.successful_requests / result.total_requests * 100:.1f}%")
        print(f"总耗时:       {result.total_duration_ms:.1f}ms")
        print(f"实际速率:     {result.requests_per_second:.2f} 请求/秒")
        print(f"平均延迟:     {result.avg_latency_ms:.1f}ms")
        print(f"最小延迟:     {result.min_latency_ms:.1f}ms")
        print(f"最大延迟:     {result.max_latency_ms:.1f}ms")
        
        if result.errors:
            print(f"\n错误类型:")
            for error in result.errors:
                print(f"  - {error}")
        print("=" * 60)


async def run_all_tests_async():
    """运行所有异步测试"""
    tester = RateLimitTester()
    
    print("\n" + "=" * 60)
    print(f"Hyperliquid 仓位获取频率限制测试（异步版本）")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试地址数: {len(TEST_ADDRESSES)}")
    print("=" * 60)
    
    all_results = []
    
    # 测试 1: 异步限速请求 - 每秒3个
    print("\n>>> 测试 1: 异步限速请求 - 每秒3个")
    result = await tester.test_rate_limited_async(TEST_ADDRESSES, requests_per_second=3)
    tester.print_result(result)
    all_results.append(result)
    
    await asyncio.sleep(2)  # 测试间隔
    
    # 测试 2: 异步并发请求 - 3个并发
    print("\n>>> 测试 2: 异步并发请求 - 3个并发")
    result = await tester.test_concurrent_async(TEST_ADDRESSES, max_concurrent=3)
    tester.print_result(result)
    all_results.append(result)
    
    await asyncio.sleep(2)
    
    # 测试 3: 异步并发请求 - 10个并发
    print("\n>>> 测试 3: 异步并发请求 - 10个并发")
    result = await tester.test_concurrent_async(TEST_ADDRESSES, max_concurrent=10)
    tester.print_result(result)
    all_results.append(result)
    
    await asyncio.sleep(2)
    
    # 测试 4: 异步突发请求 - 每批3个，批间隔1秒
    print("\n>>> 测试 4: 异步突发请求 - 每批3个，批间隔1秒")
    result = await tester.test_burst_async(TEST_ADDRESSES, burst_size=3, delay_between_bursts_ms=1000)
    tester.print_result(result)
    all_results.append(result)
    
    await asyncio.sleep(2)
    
    # 测试 5: 异步限速请求 - 每秒5个
    print("\n>>> 测试 5: 异步限速请求 - 每秒5个")
    result = await tester.test_rate_limited_async(TEST_ADDRESSES, requests_per_second=5)
    tester.print_result(result)
    all_results.append(result)
    
    await asyncio.sleep(2)
    
    # 测试 6: 异步限速请求 - 每秒10个
    print("\n>>> 测试 6: 异步限速请求 - 每秒10个")
    result = await tester.test_rate_limited_async(TEST_ADDRESSES, requests_per_second=10)
    tester.print_result(result)
    all_results.append(result)
    
    # 汇总
    print("\n\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    print(f"{'测试名称':<45} {'成功率':<10} {'速率(/s)':<10} {'平均延迟(ms)':<15}")
    print("-" * 80)
    for r in all_results:
        success_rate = f"{r.successful_requests / r.total_requests * 100:.1f}%"
        print(f"{r.test_name:<45} {success_rate:<10} {r.requests_per_second:<10.2f} {r.avg_latency_ms:<15.1f}")
    print("=" * 60)


async def test_specific_rate_async(requests_per_second: float = 3, duration_seconds: float = 5):
    """
    异步测试特定速率
    
    Args:
        requests_per_second: 每秒请求数（默认3）
        duration_seconds: 测试持续时间（秒）
    """
    tester = RateLimitTester()
    
    # 计算需要的请求数
    total_requests = int(requests_per_second * duration_seconds)
    
    # 循环使用地址
    addresses = (TEST_ADDRESSES * (total_requests // len(TEST_ADDRESSES) + 1))[:total_requests]
    
    print(f"\n异步测试特定速率: {requests_per_second} 请求/秒, 持续 {duration_seconds} 秒")
    print(f"总请求数: {total_requests}")
    
    result = await tester.test_rate_limited_async(addresses, requests_per_second=requests_per_second)
    tester.print_result(result)
    
    return result


async def test_max_concurrent_async(max_concurrent_list: List[int] = None):
    """
    异步测试不同并发数的表现
    
    Args:
        max_concurrent_list: 要测试的并发数列表
    """
    if max_concurrent_list is None:
        max_concurrent_list = [1, 3, 5, 10, 14, 20]
    
    tester = RateLimitTester()
    all_results = []
    
    print(f"\n异步测试不同并发数的表现")
    print("=" * 60)
    
    for concurrent in max_concurrent_list:
        # 循环使用地址以确保有足够的请求
        addresses = (TEST_ADDRESSES * (concurrent // len(TEST_ADDRESSES) + 1))[:max(concurrent, len(TEST_ADDRESSES))]
        
        result = await tester.test_concurrent_async(addresses, max_concurrent=concurrent)
        tester.print_result(result)
        all_results.append(result)
        
        await asyncio.sleep(2)  # 测试间隔
    
    return all_results


def create_parser() -> argparse.ArgumentParser:
    """创建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="测试 Hyperliquid 获取仓位的频率限制（异步版本）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python test_position_rate_limit.py                      # 运行所有测试
  python test_position_rate_limit.py --mode rate          # 测试限速请求（默认3/秒）
  python test_position_rate_limit.py --mode rate -r 5     # 测试5请求/秒
  python test_position_rate_limit.py --mode rate -r 3 -d 10  # 测试3请求/秒，持续10秒
  python test_position_rate_limit.py --mode concurrent    # 测试不同并发数
  python test_position_rate_limit.py --mode burst -b 3    # 测试突发请求，每批3个
        """
    )
    
    parser.add_argument(
        "--mode", "-m",
        type=str,
        choices=["all", "rate", "concurrent", "burst"],
        default="all",
        help="测试模式: all=所有测试, rate=限速测试, concurrent=并发测试, burst=突发测试 (默认: all)"
    )
    
    parser.add_argument(
        "--rate", "-r",
        type=float,
        default=3.0,
        help="每秒请求数 (默认: 3)"
    )
    
    parser.add_argument(
        "--duration", "-d",
        type=float,
        default=5.0,
        help="测试持续时间（秒）(默认: 5)"
    )
    
    parser.add_argument(
        "--concurrent", "-c",
        type=int,
        default=3,
        help="最大并发数 (默认: 3)"
    )
    
    parser.add_argument(
        "--burst-size", "-b",
        type=int,
        default=3,
        help="突发请求每批数量 (默认: 3)"
    )
    
    parser.add_argument(
        "--burst-interval", "-i",
        type=float,
        default=1000.0,
        help="突发请求批次间隔（毫秒）(默认: 1000)"
    )
    
    parser.add_argument(
        "--api-url",
        type=str,
        default=constants.MAINNET_API_URL,
        help=f"API URL (默认: {constants.MAINNET_API_URL})"
    )
    
    return parser


async def main_async(args: argparse.Namespace):
    """异步主函数"""
    tester = RateLimitTester(api_url=args.api_url)
    
    if args.mode == "all":
        await run_all_tests_async()
    
    elif args.mode == "rate":
        await test_specific_rate_async(
            requests_per_second=args.rate,
            duration_seconds=args.duration
        )
    
    elif args.mode == "concurrent":
        # 测试单个并发数或多个
        if args.concurrent > 0:
            total_requests = int(args.rate * args.duration)
            addresses = (TEST_ADDRESSES * (total_requests // len(TEST_ADDRESSES) + 1))[:max(total_requests, len(TEST_ADDRESSES))]
            
            print(f"\n异步并发测试: 并发数={args.concurrent}")
            result = await tester.test_concurrent_async(addresses, max_concurrent=args.concurrent)
            tester.print_result(result)
        else:
            await test_max_concurrent_async()
    
    elif args.mode == "burst":
        total_requests = int(args.rate * args.duration)
        addresses = (TEST_ADDRESSES * (total_requests // len(TEST_ADDRESSES) + 1))[:max(total_requests, len(TEST_ADDRESSES))]
        
        print(f"\n异步突发测试: 每批={args.burst_size}, 间隔={args.burst_interval}ms")
        result = await tester.test_burst_async(
            addresses, 
            burst_size=args.burst_size,
            delay_between_bursts_ms=args.burst_interval
        )
        tester.print_result(result)


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()
    
    asyncio.run(main_async(args))
