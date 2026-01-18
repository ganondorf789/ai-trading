"""
测试 Hyperliquid 获取仓位的频率限制
测试不同的请求频率（如每秒10个地址）
"""
import asyncio
import time
import statistics
from datetime import datetime
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from loguru import logger
from hyperliquid.info import Info
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


class RateLimitTester:
    """频率限制测试器"""
    
    def __init__(self, api_url: str = constants.MAINNET_API_URL):
        self.api_url = api_url
        self.info = Info(api_url, skip_ws=True)
        
    def fetch_user_state(self, address: str) -> RequestResult:
        """获取单个用户状态"""
        start_time = time.perf_counter()
        try:
            state = self.info.user_state(address)
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
    
    def test_sequential(self, addresses: List[str], delay_between_ms: float = 0) -> TestResult:
        """
        顺序请求测试
        
        Args:
            addresses: 地址列表
            delay_between_ms: 请求间隔（毫秒）
        """
        logger.info(f"开始顺序请求测试，地址数: {len(addresses)}，间隔: {delay_between_ms}ms")
        
        results: List[RequestResult] = []
        start_time = time.perf_counter()
        
        for i, address in enumerate(addresses):
            result = self.fetch_user_state(address)
            results.append(result)
            
            status = "✓" if result.success else "✗"
            logger.info(f"  [{i+1}/{len(addresses)}] {status} {address[:10]}... "
                       f"耗时: {result.duration_ms:.1f}ms, 仓位数: {result.positions_count}")
            
            if delay_between_ms > 0 and i < len(addresses) - 1:
                time.sleep(delay_between_ms / 1000)
        
        total_duration_ms = (time.perf_counter() - start_time) * 1000
        return self._summarize_results("顺序请求", results, total_duration_ms)
    
    def test_concurrent(self, addresses: List[str], max_workers: int = 10) -> TestResult:
        """
        并发请求测试
        
        Args:
            addresses: 地址列表
            max_workers: 最大并发数
        """
        logger.info(f"开始并发请求测试，地址数: {len(addresses)}，并发数: {max_workers}")
        
        results: List[RequestResult] = []
        start_time = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.fetch_user_state, addr): addr 
                for addr in addresses
            }
            
            for i, future in enumerate(as_completed(futures)):
                result = future.result()
                results.append(result)
                
                status = "✓" if result.success else "✗"
                logger.info(f"  [{i+1}/{len(addresses)}] {status} {result.address[:10]}... "
                           f"耗时: {result.duration_ms:.1f}ms, 仓位数: {result.positions_count}")
        
        total_duration_ms = (time.perf_counter() - start_time) * 1000
        return self._summarize_results(f"并发请求(workers={max_workers})", results, total_duration_ms)
    
    def test_burst(self, addresses: List[str], burst_size: int = 10, 
                   delay_between_bursts_ms: float = 1000) -> TestResult:
        """
        突发请求测试 - 每次发送一批请求，然后等待
        
        Args:
            addresses: 地址列表
            burst_size: 每批请求数量
            delay_between_bursts_ms: 批次间隔（毫秒）
        """
        logger.info(f"开始突发请求测试，地址数: {len(addresses)}，"
                   f"批大小: {burst_size}，批间隔: {delay_between_bursts_ms}ms")
        
        results: List[RequestResult] = []
        start_time = time.perf_counter()
        
        # 分批处理
        for batch_idx in range(0, len(addresses), burst_size):
            batch = addresses[batch_idx:batch_idx + burst_size]
            batch_num = batch_idx // burst_size + 1
            logger.info(f"  批次 {batch_num}: 发送 {len(batch)} 个请求...")
            
            # 并发发送这一批
            with ThreadPoolExecutor(max_workers=len(batch)) as executor:
                futures = {
                    executor.submit(self.fetch_user_state, addr): addr 
                    for addr in batch
                }
                
                for future in as_completed(futures):
                    result = future.result()
                    results.append(result)
                    
                    status = "✓" if result.success else "✗"
                    error_info = f" 错误: {result.error}" if result.error else ""
                    logger.info(f"    {status} {result.address[:10]}... "
                               f"耗时: {result.duration_ms:.1f}ms{error_info}")
            
            # 如果还有下一批，等待
            if batch_idx + burst_size < len(addresses):
                logger.info(f"  等待 {delay_between_bursts_ms}ms...")
                time.sleep(delay_between_bursts_ms / 1000)
        
        total_duration_ms = (time.perf_counter() - start_time) * 1000
        return self._summarize_results(
            f"突发请求(burst={burst_size}, interval={delay_between_bursts_ms}ms)", 
            results, total_duration_ms
        )
    
    def test_rate_limited(self, addresses: List[str], 
                          requests_per_second: float = 10) -> TestResult:
        """
        限速请求测试 - 控制每秒请求数
        
        Args:
            addresses: 地址列表
            requests_per_second: 每秒请求数
        """
        logger.info(f"开始限速请求测试，地址数: {len(addresses)}，"
                   f"目标速率: {requests_per_second} 请求/秒")
        
        results: List[RequestResult] = []
        start_time = time.perf_counter()
        interval = 1.0 / requests_per_second  # 请求间隔（秒）
        
        for i, address in enumerate(addresses):
            request_start = time.perf_counter()
            
            result = self.fetch_user_state(address)
            results.append(result)
            
            status = "✓" if result.success else "✗"
            logger.info(f"  [{i+1}/{len(addresses)}] {status} {address[:10]}... "
                       f"耗时: {result.duration_ms:.1f}ms, 仓位数: {result.positions_count}")
            
            # 计算需要等待的时间以维持目标速率
            elapsed = time.perf_counter() - request_start
            sleep_time = interval - elapsed
            if sleep_time > 0 and i < len(addresses) - 1:
                time.sleep(sleep_time)
        
        total_duration_ms = (time.perf_counter() - start_time) * 1000
        return self._summarize_results(
            f"限速请求({requests_per_second}/s)", 
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


def run_all_tests():
    """运行所有测试"""
    tester = RateLimitTester()
    
    print("\n" + "=" * 60)
    print(f"Hyperliquid 仓位获取频率限制测试")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试地址数: {len(TEST_ADDRESSES)}")
    print("=" * 60)
    
    all_results = []
    
    # 测试 1: 顺序请求（无间隔）
    print("\n>>> 测试 1: 顺序请求（无间隔）")
    result = tester.test_sequential(TEST_ADDRESSES, delay_between_ms=0)
    tester.print_result(result)
    all_results.append(result)
    
    time.sleep(2)  # 测试间隔
    
    # 测试 2: 10个并发请求
    print("\n>>> 测试 2: 10个并发请求")
    result = tester.test_concurrent(TEST_ADDRESSES, max_workers=10)
    tester.print_result(result)
    all_results.append(result)
    
    time.sleep(2)
    
    # 测试 3: 14个并发请求（所有地址同时）
    print("\n>>> 测试 3: 14个并发请求（所有地址同时）")
    result = tester.test_concurrent(TEST_ADDRESSES, max_workers=14)
    tester.print_result(result)
    all_results.append(result)
    
    time.sleep(2)
    
    # 测试 4: 突发请求 - 每秒10个
    print("\n>>> 测试 4: 突发请求 - 每批10个，批间隔1秒")
    result = tester.test_burst(TEST_ADDRESSES, burst_size=10, delay_between_bursts_ms=1000)
    tester.print_result(result)
    all_results.append(result)
    
    time.sleep(2)
    
    # 测试 5: 限速请求 - 每秒10个
    print("\n>>> 测试 5: 限速请求 - 每秒10个")
    result = tester.test_rate_limited(TEST_ADDRESSES, requests_per_second=10)
    tester.print_result(result)
    all_results.append(result)
    
    time.sleep(2)
    
    # 测试 6: 限速请求 - 每秒20个
    print("\n>>> 测试 6: 限速请求 - 每秒20个")
    result = tester.test_rate_limited(TEST_ADDRESSES, requests_per_second=20)
    tester.print_result(result)
    all_results.append(result)
    
    # 汇总
    print("\n\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    print(f"{'测试名称':<40} {'成功率':<10} {'速率(/s)':<10} {'平均延迟(ms)':<15}")
    print("-" * 75)
    for r in all_results:
        success_rate = f"{r.successful_requests / r.total_requests * 100:.1f}%"
        print(f"{r.test_name:<40} {success_rate:<10} {r.requests_per_second:<10.2f} {r.avg_latency_ms:<15.1f}")
    print("=" * 60)


def test_specific_rate(requests_per_second: float = 10, duration_seconds: float = 5):
    """
    测试特定速率
    
    Args:
        requests_per_second: 每秒请求数
        duration_seconds: 测试持续时间（秒）
    """
    tester = RateLimitTester()
    
    # 计算需要的请求数
    total_requests = int(requests_per_second * duration_seconds)
    
    # 循环使用地址
    addresses = (TEST_ADDRESSES * (total_requests // len(TEST_ADDRESSES) + 1))[:total_requests]
    
    print(f"\n测试特定速率: {requests_per_second} 请求/秒, 持续 {duration_seconds} 秒")
    print(f"总请求数: {total_requests}")
    
    result = tester.test_rate_limited(addresses, requests_per_second=requests_per_second)
    tester.print_result(result)
    
    return result


def test_max_concurrent(max_workers_list: List[int] = None):
    """
    测试不同并发数的表现
    
    Args:
        max_workers_list: 要测试的并发数列表
    """
    if max_workers_list is None:
        max_workers_list = [1, 5, 10, 14, 20, 30]
    
    tester = RateLimitTester()
    all_results = []
    
    print(f"\n测试不同并发数的表现")
    print("=" * 60)
    
    for workers in max_workers_list:
        # 循环使用地址以确保有足够的请求
        addresses = (TEST_ADDRESSES * (workers // len(TEST_ADDRESSES) + 1))[:max(workers, len(TEST_ADDRESSES))]
        
        result = tester.test_concurrent(addresses, max_workers=workers)
        tester.print_result(result)
        all_results.append(result)
        
        time.sleep(2)  # 测试间隔
    
    return all_results


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "rate":
            # 测试特定速率: python test_position_rate_limit.py rate 10 5
            rate = float(sys.argv[2]) if len(sys.argv) > 2 else 10
            duration = float(sys.argv[3]) if len(sys.argv) > 3 else 5
            test_specific_rate(rate, duration)
        elif sys.argv[1] == "concurrent":
            # 测试并发: python test_position_rate_limit.py concurrent
            test_max_concurrent()
        else:
            print("用法:")
            print("  python test_position_rate_limit.py          # 运行所有测试")
            print("  python test_position_rate_limit.py rate 10 5  # 测试10请求/秒，持续5秒")
            print("  python test_position_rate_limit.py concurrent # 测试不同并发数")
    else:
        run_all_tests()
