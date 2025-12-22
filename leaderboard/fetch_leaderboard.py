"""
Hyperliquid Leaderboard Scraper
直接调用Hyperliquid的stats-data API获取排行榜上所有交易者的地址
"""
import requests
import json
from typing import List, Dict, Any, Optional


def fetch_leaderboard(save_to_file: bool = True) -> List[Dict[str, Any]]:
    """
    获取Hyperliquid排行榜数据

    Returns:
        List of trader data with ethAddress, accountValue, windowPerformances, etc.
    """
    url = "https://stats-data.hyperliquid.xyz/Mainnet/leaderboard"

    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()

        leaderboard_rows = data.get("leaderboardRows", [])
        print(f"获取到 {len(leaderboard_rows)} 个交易者")

        if save_to_file:
            # 保存完整数据
            with open("leaderboard_full.json", "w", encoding="utf-8") as f:
                json.dump(leaderboard_rows, f, indent=2, ensure_ascii=False)
            print("完整数据已保存到 leaderboard_full.json")

            # 只保存地址
            addresses = [row["ethAddress"] for row in leaderboard_rows]
            with open("leaderboard_addresses.txt", "w") as f:
                f.write("\n".join(addresses))
            print(f"地址已保存到 leaderboard_addresses.txt")

        return leaderboard_rows

    except requests.RequestException as e:
        print(f"请求失败: {e}")
        return []


def get_top_traders(
    sort_by: str = "pnl",
    window: str = "allTime",
    limit: int = 100,
    min_pnl: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    获取排名靠前的交易者

    Args:
        sort_by: 排序字段 - pnl, roi, vlm, accountValue
        window: 时间窗口 - day, week, month, allTime
        limit: 返回数量
        min_pnl: 最低盈利过滤

    Returns:
        排序后的交易者列表
    """
    rows = fetch_leaderboard(save_to_file=False)

    if not rows:
        return []

    # 提取并添加指定窗口的性能数据
    for row in rows:
        performances = dict(row.get("windowPerformances", []))
        window_data = performances.get(window, {})
        row["pnl"] = float(window_data.get("pnl", 0))
        row["roi"] = float(window_data.get("roi", 0))
        row["vlm"] = float(window_data.get("vlm", 0))

    # 过滤
    if min_pnl is not None:
        rows = [r for r in rows if r["pnl"] >= min_pnl]

    # 排序
    if sort_by == "accountValue":
        rows.sort(key=lambda x: float(x.get("accountValue", 0)), reverse=True)
    else:
        rows.sort(key=lambda x: x.get(sort_by, 0), reverse=True)

    return rows[:limit]


def print_trader_summary(traders: List[Dict[str, Any]], window: str = "allTime"):
    """打印交易者摘要"""
    print(f"\n{'='*80}")
    print(f"{'排名':<6}{'地址':<44}{'账户价值':>15}{'PnL':>15}{'ROI':>10}")
    print(f"{'='*80}")

    for i, trader in enumerate(traders, 1):
        addr = trader["ethAddress"]
        display_name = trader.get("displayName")
        if display_name:
            addr = f"{display_name} ({addr[:6]}...{addr[-4:]})"
        else:
            addr = f"{addr[:10]}...{addr[-6:]}"

        account_value = float(trader.get("accountValue", 0))
        pnl = trader.get("pnl", 0)
        roi = trader.get("roi", 0)

        print(f"{i:<6}{addr:<44}${account_value:>14,.0f}${pnl:>14,.0f}{roi:>9.2%}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Hyperliquid Leaderboard Scraper")
    parser.add_argument("--top", type=int, default=50, help="显示前N个交易者")
    parser.add_argument("--sort", choices=["pnl", "roi", "vlm", "accountValue"],
                        default="pnl", help="排序字段")
    parser.add_argument("--window", choices=["day", "week", "month", "allTime"],
                        default="allTime", help="时间窗口")
    parser.add_argument("--min-pnl", type=float, help="最低盈利过滤")
    parser.add_argument("--save", action="store_true", help="保存到文件")
    parser.add_argument("--addresses-only", action="store_true",
                        help="只输出地址列表")

    args = parser.parse_args()

    if args.save:
        # 保存所有数据
        fetch_leaderboard(save_to_file=True)
    elif args.addresses_only:
        # 只输出地址
        rows = fetch_leaderboard(save_to_file=False)
        for row in rows:
            print(row["ethAddress"])
    else:
        # 显示排行榜
        traders = get_top_traders(
            sort_by=args.sort,
            window=args.window,
            limit=args.top,
            min_pnl=args.min_pnl
        )
        print_trader_summary(traders, args.window)

        print(f"\n共 {len(traders)} 个交易者")
        print("\n提示: 使用 --save 保存完整数据到文件")
        print("      使用 --addresses-only 只输出地址列表")
