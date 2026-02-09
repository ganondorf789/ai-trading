"""
测试脚本：获取交易地址的历史成交、资金费历史、历史委托
仅用于测试，不执行任何交易操作

用法:
    # 使用 .env 中的默认钱包地址
    python test_account_history.py

    # 指定钱包地址
    python test_account_history.py --address 0x1234...

    # 指定时间范围（天数，默认7天）
    python test_account_history.py --days 30

    # 指定币种查看资金费
    python test_account_history.py --coin BTC

    # 限制返回数量
    python test_account_history.py --limit 20
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from hyperliquid.info import Info
from hyperliquid.utils import constants


# ==================== 格式化工具 ====================

def format_timestamp(ts_ms: int) -> str:
    """将毫秒时间戳转换为可读时间字符串 (UTC+8)"""
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone(timedelta(hours=8)))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def format_usd(value: float) -> str:
    """格式化 USD 金额"""
    if abs(value) >= 1000:
        return f"${value:,.2f}"
    return f"${value:.4f}"


def format_size(value: float) -> str:
    """格式化数量"""
    if value == int(value):
        return f"{int(value)}"
    return f"{value:.6g}"


def print_separator(title: str = "", char: str = "=", width: int = 100):
    """打印分隔线"""
    if title:
        padding = (width - len(title) - 2) // 2
        print(f"\n{char * padding} {title} {char * padding}")
    else:
        print(char * width)


# ==================== 历史成交 ====================

def fetch_and_display_fills(info: Info, address: str, start_ms: int, end_ms: int, limit: int):
    """获取并展示历史成交记录"""
    print_separator("历史成交 (User Fills)")

    try:
        fills = info.user_fills_by_time(address, start_ms, end_ms)
    except Exception as e:
        print(f"  获取历史成交失败: {e}")
        return

    if not fills:
        print("  无成交记录")
        return

    # 按时间倒序排列，取最近的 limit 条
    fills.sort(key=lambda x: x.get("time", 0), reverse=True)
    fills = fills[:limit]

    print(f"  共获取 {len(fills)} 条成交记录\n")

    # 汇总统计
    total_volume = 0.0
    total_fee = 0.0
    total_pnl = 0.0
    coin_stats = {}

    # 表头
    header = f"  {'时间':<22} {'币种':<8} {'方向':<6} {'价格':>14} {'数量':>12} {'成交额':>14} {'已实现PnL':>14} {'手续费':>10}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    for fill in fills:
        coin = fill.get("coin", "?")
        side = "买入" if fill.get("side") == "B" else "卖出"
        px = float(fill.get("px", 0))
        sz = float(fill.get("sz", 0))
        closed_pnl = float(fill.get("closedPnl", 0))
        fee = float(fill.get("fee", 0))
        time_str = format_timestamp(fill.get("time", 0))
        volume = px * sz

        total_volume += volume
        total_fee += fee
        total_pnl += closed_pnl

        if coin not in coin_stats:
            coin_stats[coin] = {"count": 0, "volume": 0, "pnl": 0, "fee": 0}
        coin_stats[coin]["count"] += 1
        coin_stats[coin]["volume"] += volume
        coin_stats[coin]["pnl"] += closed_pnl
        coin_stats[coin]["fee"] += fee

        pnl_str = f"{closed_pnl:+.4f}" if closed_pnl != 0 else "0"
        print(f"  {time_str:<22} {coin:<8} {side:<6} {format_usd(px):>14} {format_size(sz):>12} {format_usd(volume):>14} {pnl_str:>14} {fee:.4f}")

    # 汇总
    print()
    print_separator("成交汇总", "-", 80)
    print(f"  总成交笔数: {len(fills)}")
    print(f"  总成交额:   {format_usd(total_volume)}")
    print(f"  总已实现PnL: {format_usd(total_pnl)}")
    print(f"  总手续费:   {format_usd(total_fee)}")

    if coin_stats:
        print(f"\n  {'币种':<10} {'笔数':>6} {'成交额':>16} {'已实现PnL':>16} {'手续费':>12}")
        print("  " + "-" * 60)
        for coin, stats in sorted(coin_stats.items(), key=lambda x: x[1]["volume"], reverse=True):
            print(f"  {coin:<10} {stats['count']:>6} {format_usd(stats['volume']):>16} {format_usd(stats['pnl']):>16} {format_usd(stats['fee']):>12}")


# ==================== 资金费历史 ====================

def fetch_and_display_funding(info: Info, address: str, start_ms: int, end_ms: int, limit: int, coin: str = None):
    """获取并展示用户资金费历史"""
    print_separator("资金费历史 (User Funding History)")

    try:
        funding_records = info.user_funding_history(address, start_ms, end_ms)
    except Exception as e:
        print(f"  获取资金费历史失败: {e}")
        return

    if not funding_records:
        print("  无资金费记录")
        return

    # 提取 funding 详细数据
    all_entries = []
    for record in funding_records:
        delta = record.get("delta", {})
        entry = {
            "time": record.get("time", 0),
            "coin": delta.get("coin", "?"),
            "funding_rate": delta.get("fundingRate", "0"),
            "usdc": float(delta.get("usdc", 0)),
            "szi": float(delta.get("szi", 0)),
            "hash": record.get("hash", ""),
        }
        # 如果指定了币种，则过滤
        if coin and entry["coin"].upper() != coin.upper():
            continue
        all_entries.append(entry)

    if not all_entries:
        print(f"  无资金费记录" + (f" (币种: {coin})" if coin else ""))
        return

    # 按时间倒序
    all_entries.sort(key=lambda x: x["time"], reverse=True)
    all_entries = all_entries[:limit]

    print(f"  共获取 {len(all_entries)} 条资金费记录" + (f" (币种: {coin})" if coin else "") + "\n")

    # 表头
    header = f"  {'时间':<22} {'币种':<8} {'资金费率':>14} {'持仓数量':>14} {'资金费(USDC)':>16}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    total_funding = 0.0
    coin_funding = {}

    for entry in all_entries:
        time_str = format_timestamp(entry["time"])
        c = entry["coin"]
        rate = entry["funding_rate"]
        usdc = entry["usdc"]
        szi = entry["szi"]

        total_funding += usdc

        if c not in coin_funding:
            coin_funding[c] = 0.0
        coin_funding[c] += usdc

        usdc_str = f"{usdc:+.6f}"
        print(f"  {time_str:<22} {c:<8} {rate:>14} {format_size(szi):>14} {usdc_str:>16}")

    # 汇总
    print()
    print_separator("资金费汇总", "-", 80)
    print(f"  总资金费收支: {format_usd(total_funding)} USDC")

    if coin_funding:
        print(f"\n  {'币种':<10} {'资金费合计(USDC)':>20}")
        print("  " + "-" * 30)
        for c, total in sorted(coin_funding.items(), key=lambda x: abs(x[1]), reverse=True):
            print(f"  {c:<10} {total:>+20.6f}")


# ==================== 历史委托 ====================

def fetch_and_display_orders(info: Info, address: str, limit: int):
    """获取并展示历史委托"""
    print_separator("历史委托 (Historical Orders)")

    try:
        orders = info.historical_orders(address)
    except Exception as e:
        print(f"  获取历史委托失败: {e}")
        return

    if not orders:
        print("  无历史委托")
        return

    # 按 statusTimestamp 倒序排列
    orders.sort(
        key=lambda x: x.get("statusTimestamp", x.get("order", {}).get("timestamp", 0)),
        reverse=True
    )
    orders = orders[:limit]

    print(f"  共获取 {len(orders)} 条历史委托\n")

    # 表头
    header = f"  {'下单时间':<22} {'币种':<8} {'方向':<6} {'类型':<22} {'限价':>14} {'委托量':>10} {'原始量':>10} {'状态':<10} {'OID'}"
    print(header)
    print("  " + "-" * 130)

    status_stats = {}
    coin_stats = {}

    STATUS_MAP = {
        "open": "未成交",
        "canceled": "已取消",
        "filled": "已成交",
        "triggered": "已触发",
        "rejected": "已拒绝",
        "marginCanceled": "保证金取消",
    }

    for record in orders:
        order = record.get("order", {})
        status_raw = record.get("status", "unknown")
        status_ts = record.get("statusTimestamp", 0)

        coin = order.get("coin", "?")
        side = "买入" if order.get("side") == "B" else "卖出"
        limit_px = order.get("limitPx", "N/A")
        sz = order.get("sz", "0")
        orig_sz = order.get("origSz", sz)
        oid = order.get("oid", "?")
        timestamp = order.get("timestamp", 0)
        time_str = format_timestamp(timestamp) if timestamp else "N/A"

        # 委托类型
        order_type = order.get("orderType", "Limit")
        trigger_cond = order.get("triggerCondition", "")

        # 如果是触发单，附加触发条件
        type_str = order_type
        if order.get("isTrigger") and trigger_cond:
            type_str = f"{order_type}"

        # 状态翻译
        status_str = STATUS_MAP.get(status_raw, status_raw)

        # 补充信息：reduce_only / position tp/sl
        tags = []
        if order.get("reduceOnly"):
            tags.append("只减仓")
        if order.get("isPositionTpsl"):
            tags.append("仓位止盈止损")
        if tags:
            status_str += f" ({','.join(tags)})"

        # 统计
        status_stats[STATUS_MAP.get(status_raw, status_raw).split(" ")[0]] = \
            status_stats.get(STATUS_MAP.get(status_raw, status_raw).split(" ")[0], 0) + 1
        coin_stats[coin] = coin_stats.get(coin, 0) + 1

        # 截断过长的类型字符串
        if len(type_str) > 22:
            type_str = type_str[:19] + "..."

        print(f"  {time_str:<22} {coin:<8} {side:<6} {type_str:<22} {limit_px:>14} {sz:>10} {orig_sz:>10} {status_str}")

    # 汇总
    print()
    print_separator("委托汇总", "-", 80)
    print(f"  总委托数: {len(orders)}")

    print(f"\n  按状态:")
    for status, count in sorted(status_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"    {status}: {count}")

    print(f"\n  按币种:")
    for coin, count in sorted(coin_stats.items(), key=lambda x: x[1], reverse=True):
        print(f"    {coin}: {count}")


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(description="获取 Hyperliquid 交易地址的历史数据（仅测试用）")
    parser.add_argument("--address", "-a", type=str, default=None,
                        help="钱包地址（默认从 .env 读取 HYPERLIQUID_WALLET_ADDRESS）")
    parser.add_argument("--days", "-d", type=int, default=7,
                        help="查询最近 N 天的数据（默认 7 天）")
    parser.add_argument("--coin", "-c", type=str, default=None,
                        help="筛选指定币种的资金费记录（如 BTC, ETH）")
    parser.add_argument("--limit", "-l", type=int, default=50,
                        help="每类数据最多展示条数（默认 50）")
    parser.add_argument("--section", "-s", type=str, default="all",
                        choices=["all", "fills", "funding", "orders"],
                        help="选择查看的部分: all/fills/funding/orders（默认 all）")
    parser.add_argument("--raw", action="store_true",
                        help="输出原始 JSON 数据（调试用）")
    args = parser.parse_args()

    # 加载环境变量
    load_dotenv()

    # 确定钱包地址
    address = args.address or os.getenv("HYPERLIQUID_WALLET_ADDRESS")
    if not address:
        print("错误: 未指定钱包地址。请通过 --address 参数或 .env 中的 HYPERLIQUID_WALLET_ADDRESS 配置。")
        sys.exit(1)

    # 时间范围
    now = datetime.now(tz=timezone.utc)
    start_time = now - timedelta(days=args.days)
    start_ms = int(start_time.timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)

    print_separator("Hyperliquid 账户历史查询")
    print(f"  钱包地址: {address}")
    print(f"  查询范围: 最近 {args.days} 天")
    print(f"  起始时间: {start_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"  结束时间: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    if args.coin:
        print(f"  筛选币种: {args.coin}")
    print(f"  每类限制: {args.limit} 条")

    # 初始化 Info 客户端（只读，无需私钥）
    info = Info(constants.MAINNET_API_URL, skip_ws=True)

    # 如果指定 --raw 模式，输出原始 JSON
    if args.raw:
        print_separator("原始数据 (RAW JSON)")

        if args.section in ("all", "fills"):
            print("\n--- user_fills_by_time ---")
            try:
                fills = info.user_fills_by_time(address, start_ms, end_ms)
                print(json.dumps(fills[:args.limit], indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"Error: {e}")

        if args.section in ("all", "funding"):
            print("\n--- user_funding_history ---")
            try:
                funding = info.user_funding_history(address, start_ms, end_ms)
                print(json.dumps(funding[:args.limit], indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"Error: {e}")

        if args.section in ("all", "orders"):
            print("\n--- historical_orders ---")
            try:
                orders = info.historical_orders(address)
                print(json.dumps(orders[:args.limit], indent=2, ensure_ascii=False))
            except Exception as e:
                print(f"Error: {e}")
        return

    # 正常展示
    if args.section in ("all", "fills"):
        fetch_and_display_fills(info, address, start_ms, end_ms, args.limit)

    if args.section in ("all", "funding"):
        fetch_and_display_funding(info, address, start_ms, end_ms, args.limit, args.coin)

    if args.section in ("all", "orders"):
        fetch_and_display_orders(info, address, args.limit)

    print()
    print_separator()
    print("  查询完成")
    print_separator()


if __name__ == "__main__":
    main()
