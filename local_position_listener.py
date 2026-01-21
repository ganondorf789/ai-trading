#!/usr/bin/env python3
"""
本地新仓位监听器（Redis Pub/Sub）

监听服务器 Redis 推送，检测到新仓位时自动打开 Hyperliquid 详情页

使用:
  python local_position_listener.py
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

from config.settings import settings

CHANNEL = "new_positions"


def listen(auto_open: bool = True):
    """监听 Redis channel"""
    cfg = settings.redis
    print(f"""
╔═══════════════════════════════════════════════════╗
║      🎧 新仓位监听器 (Redis Pub/Sub)              ║
╚═══════════════════════════════════════════════════╝

  Redis: {cfg.host}:{cfg.port}
  自动打开: {'是' if auto_open else '否'}
""")
    
    try:
        r = redis.Redis(
            host=cfg.host, 
            port=cfg.port, 
            password=cfg.password or None, 
            db=cfg.db, 
            decode_responses=True
        )
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
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    
    args = parser.parse_args()
    listen(not args.no_open)


if __name__ == "__main__":
    main()
