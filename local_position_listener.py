#!/usr/bin/env python3
"""
本地新仓位监听器（Redis Pub/Sub）

监听服务器 Redis 推送，检测到新仓位时自动打开 Hyperliquid 详情页

使用:
  python local_position_listener.py
  python local_position_listener.py --host your-redis-server --port 6380
  python local_position_listener.py --no-open  # 仅显示，不打开浏览器
"""
import argparse
import webbrowser
from datetime import datetime

try:
    import redis
except ImportError:
    print("请先安装 redis: pip install redis")
    exit(1)

CHANNEL = "new_positions"


def listen(host: str, port: int, password: str = None, db: int = 0, auto_open: bool = True):
    """监听 Redis channel"""
    print(f"""
╔═══════════════════════════════════════════════════╗
║      🎧 新仓位监听器 (Redis Pub/Sub)              ║
╚═══════════════════════════════════════════════════╝

  Redis: {host}:{port}
  自动打开: {'是' if auto_open else '否'}
""")
    
    try:
        r = redis.Redis(host=host, port=port, password=password, db=db, decode_responses=True)
        r.ping()
        print(f"✓ 已连接，等待新仓位...\n")
    except redis.ConnectionError as e:
        print(f"✗ 连接失败: {e}")
        return
    
    pubsub = r.pubsub()
    pubsub.subscribe(CHANNEL)
    
    try:
        for msg in pubsub.listen():
            if msg['type'] == 'message':
                url = msg['data']
                ts = datetime.now().strftime('%H:%M:%S')
                print(f"[{ts}] ⚡ {url}")
                if auto_open:
                    webbrowser.open(url)
    except KeyboardInterrupt:
        print("\n👋 退出")
    finally:
        pubsub.close()


def main():
    parser = argparse.ArgumentParser(description="本地新仓位监听器")
    parser.add_argument("--host", default="localhost", help="Redis 主机 (默认: localhost)")
    parser.add_argument("--port", type=int, default=6380, help="Redis 端口 (默认: 6380)")
    parser.add_argument("--password", default=None, help="Redis 密码")
    parser.add_argument("--db", type=int, default=0, help="Redis DB (默认: 0)")
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    
    args = parser.parse_args()
    listen(args.host, args.port, args.password, args.db, not args.no_open)


if __name__ == "__main__":
    main()
