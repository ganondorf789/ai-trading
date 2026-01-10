"""
重试获取失败的交易记录脚本

功能说明：
1. 从 fetch_fails 表读取待处理的失败记录
2. 根据失败类型和时间范围重新获取数据
3. 成功后标记为已解决，失败则更新重试次数
4. 支持按地址、类型筛选，支持设置最大重试次数
"""
import sys
from pathlib import Path
import pendulum
from loguru import logger
import time
from typing import List, Dict, Optional
import argparse

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from screener.api_client import SyncAPIClient
from screener.config import APIConfig
from screener.utils import SHANGHAI_TZ, timestamp_to_pendulum
from database import TraderDatabase


def retry_single_fail(
    client: SyncAPIClient,
    db: TraderDatabase,
    fail_record: Dict,
    max_retries: int = 5
) -> bool:
    """
    重试单个失败记录
    
    Args:
        client: API 客户端
        db: 数据库实例
        fail_record: 失败记录
        max_retries: 最大重试次数
    
    Returns:
        是否成功
    """
    fail_id = fail_record['id']
    address = fail_record['address']
    fail_type = fail_record['fail_type']
    start_time = fail_record.get('start_time')
    end_time = fail_record.get('end_time')
    retry_count = fail_record.get('retry_count', 0)
    
    # 检查是否超过最大重试次数
    if retry_count >= max_retries:
        logger.warning(f"  ⏭ 记录 #{fail_id} 已达最大重试次数 ({retry_count}/{max_retries})，标记为失败")
        db.mark_as_failed(fail_id, f"达到最大重试次数 {max_retries}")
        return False
    
    # 增加重试次数
    db.increment_retry_count(fail_id)
    
    try:
        if fail_type == 'recent':
            # 获取最近的记录
            logger.info(f"  重试获取最近 2000 条记录...")
            fills = client.get_user_fills(address, limit=0)
        else:
            # 获取指定时间范围的记录
            if not start_time or not end_time:
                logger.error(f"  ✗ 缺少时间范围信息")
                db.mark_as_failed(fail_id, "缺少时间范围信息")
                return False
            
            start_dt = timestamp_to_pendulum(start_time)
            end_dt = timestamp_to_pendulum(end_time)
            
            logger.info(
                f"  重试获取 [{fail_type}] {start_dt.format('YYYY-MM-DD HH:mm')} "
                f"至 {end_dt.format('YYYY-MM-DD HH:mm')}..."
            )
            
            fills = client.get_user_fills_by_time(address, start_time, end_time)
        
        if fills:
            # 保存获取到的数据
            saved_count = db.save_fills(address, fills)
            logger.success(f"  ✓ 获取 {len(fills)} 条，保存 {saved_count} 条")
            
            # 标记为已解决
            db.mark_as_resolved(fail_id)
            return True
        else:
            # 没有数据也算成功（可能确实没有交易）
            logger.info(f"  ✓ 没有数据（时间范围内可能确实没有交易）")
            db.mark_as_resolved(fail_id)
            return True
            
    except Exception as e:
        error_msg = f"重试失败: {repr(e)}"
        logger.error(f"  ✗ {error_msg}")
        db.update_fail_status(fail_id, 'pending', error_msg)
        return False


def retry_by_address(
    client: SyncAPIClient,
    db: TraderDatabase,
    address: str,
    max_retries: int = 5
) -> Dict:
    """
    重试某个地址的所有失败记录
    
    Args:
        client: API 客户端
        db: 数据库实例
        address: 交易者地址
        max_retries: 最大重试次数
    
    Returns:
        处理结果统计
    """
    fails = db.get_pending_fails(address=address)
    
    if not fails:
        logger.info(f"地址 {address[:16]}... 没有待处理的失败记录")
        return {'total': 0, 'success': 0, 'failed': 0}
    
    logger.info(f"地址 {address[:16]}... 有 {len(fails)} 条待处理的失败记录")
    
    success_count = 0
    failed_count = 0
    
    for i, fail in enumerate(fails, 1):
        logger.info(f"[{i}/{len(fails)}] 处理记录 #{fail['id']} [{fail['fail_type']}]")
        
        if retry_single_fail(client, db, fail, max_retries):
            success_count += 1
        else:
            failed_count += 1
        
        # 每次请求后等待
        time.sleep(3.0)
    
    return {
        'total': len(fails),
        'success': success_count,
        'failed': failed_count
    }


def main():
    parser = argparse.ArgumentParser(description="重试获取失败的交易记录")
    parser.add_argument(
        "--address", "-a",
        type=str,
        help="只处理指定地址的失败记录"
    )
    parser.add_argument(
        "--type", "-t",
        type=str,
        choices=['recent', 'month', 'week', 'day', 'hour'],
        help="只处理指定类型的失败记录"
    )
    parser.add_argument(
        "--max-retries", "-r",
        type=int,
        default=5,
        help="最大重试次数（默认: 5）"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=100,
        help="处理的最大记录数（默认: 100）"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="仅显示待处理的失败记录，不执行重试"
    )
    parser.add_argument(
        "--summary", "-s",
        action="store_true",
        help="仅显示失败记录汇总统计"
    )
    parser.add_argument(
        "--clear-resolved",
        type=int,
        metavar="DAYS",
        help="清除指定天数前的已解决记录"
    )
    
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("交易记录获取失败重试工具")
    logger.info("=" * 80)
    
    # 初始化数据库
    logger.info("初始化数据库连接...")
    db = TraderDatabase()
    
    # 清除旧的已解决记录
    if args.clear_resolved:
        deleted = db.delete_resolved_fails(args.clear_resolved)
        logger.info(f"已删除 {deleted} 条 {args.clear_resolved} 天前的已解决记录")
        db.close()
        return
    
    # 显示汇总统计
    if args.summary:
        summary = db.get_fails_summary()
        
        logger.info("")
        logger.info("失败记录汇总统计:")
        logger.info("-" * 40)
        logger.info(f"待处理:   {summary['total_pending']}")
        logger.info(f"已解决:   {summary['total_resolved']}")
        logger.info(f"永久失败: {summary['total_failed']}")
        
        if summary['by_type']:
            logger.info("")
            logger.info("按类型统计（待处理）:")
            for fail_type, count in summary['by_type'].items():
                logger.info(f"  {fail_type}: {count}")
        
        if summary['by_address']:
            logger.info("")
            logger.info("按地址统计（待处理，前20）:")
            for item in summary['by_address']:
                logger.info(f"  {item['address'][:16]}... : {item['count']}")
        
        db.close()
        return
    
    # 获取待处理的失败记录
    fails = db.get_pending_fails(
        address=args.address,
        fail_type=args.type,
        limit=args.limit
    )
    
    if not fails:
        logger.info("没有待处理的失败记录")
        db.close()
        return
    
    logger.info(f"找到 {len(fails)} 条待处理的失败记录")
    logger.info("")
    
    # 显示失败记录
    for i, fail in enumerate(fails[:20], 1):  # 最多显示前20条
        start_dt = timestamp_to_pendulum(fail['start_time']) if fail.get('start_time') else None
        end_dt = timestamp_to_pendulum(fail['end_time']) if fail.get('end_time') else None
        
        time_range = ""
        if start_dt and end_dt:
            time_range = f"{start_dt.format('MM-DD HH:mm')} ~ {end_dt.format('MM-DD HH:mm')}"
        
        logger.info(
            f"  {i:>2}. #{fail['id']} | {fail['address'][:12]}... | "
            f"{fail['fail_type']:>6} | 重试: {fail.get('retry_count', 0)} | "
            f"{time_range}"
        )
    
    if len(fails) > 20:
        logger.info(f"  ... 还有 {len(fails) - 20} 条记录")
    
    if args.dry_run:
        logger.info("")
        logger.info("预览模式，已退出")
        db.close()
        return
    
    # 确认执行
    logger.info("")
    logger.info("准备开始重试...")
    logger.info("等待 5 秒后开始（按 Ctrl+C 取消）")
    try:
        time.sleep(5)
    except KeyboardInterrupt:
        logger.warning("\n用户取消")
        db.close()
        return
    
    # 初始化 API 客户端
    logger.info("")
    logger.info("初始化 API 客户端...")
    
    config = APIConfig()
    config.api_call_delay = 3.0
    config.max_retries = 5
    config.retry_delay = 3.0
    
    max_init_retries = 3
    client = None
    
    for retry in range(max_init_retries):
        try:
            client = SyncAPIClient(config)
            logger.success("✓ API 客户端初始化成功")
            break
        except Exception as e:
            if retry < max_init_retries - 1:
                wait_time = (retry + 1) * 10
                logger.warning(f"API 客户端初始化失败，等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                logger.error(f"API 客户端初始化失败: {str(e)}")
                db.close()
                return
    
    if not client:
        db.close()
        return
    
    # 处理统计
    total_processed = 0
    success_count = 0
    failed_count = 0
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("开始处理失败记录")
    logger.info("=" * 80)
    
    for i, fail in enumerate(fails, 1):
        logger.info("")
        logger.info(f"[{i}/{len(fails)}] 处理记录 #{fail['id']}")
        logger.info(f"  地址: {fail['address'][:24]}...")
        logger.info(f"  类型: {fail['fail_type']}")
        logger.info(f"  重试次数: {fail.get('retry_count', 0)}/{args.max_retries}")
        
        try:
            if retry_single_fail(client, db, fail, args.max_retries):
                success_count += 1
            else:
                failed_count += 1
            
            total_processed += 1
            
        except KeyboardInterrupt:
            logger.warning("\n用户中断")
            break
        except Exception as e:
            logger.error(f"  ✗ 处理异常: {repr(e)}")
            failed_count += 1
            continue
        
        # 每次请求后等待
        if i < len(fails):
            time.sleep(3.0)
    
    # 汇总统计
    logger.info("")
    logger.info("=" * 80)
    logger.info("处理完成")
    logger.info("=" * 80)
    logger.info(f"处理记录: {total_processed} 条")
    logger.info(f"成功:     {success_count} 条")
    logger.info(f"失败:     {failed_count} 条")
    
    # 显示剩余待处理
    remaining = db.get_fails_summary()
    logger.info(f"剩余待处理: {remaining['total_pending']} 条")
    
    db.close()


if __name__ == "__main__":
    main()
