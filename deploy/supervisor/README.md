# Supervisor 服务管理

## 服务列表

| 服务名 | 说明 | 优先级 | 自动启动 |
|--------|------|--------|----------|
| `api_server` | API 服务器 | 90 | 是 |
| `position_copy_trading` | 仓位级别跟单机器人 | 100 | 是 |
| `monitor_positions` | S级交易员仓位监控 | 110 | 是 |
| `screen_leaderboard` | 排行榜交易者批量分析 | 200 | 否 |
| `refresh_stale_traders` | 交易者过期数据刷新 | 210 | 否 |

## 批量分析任务说明

### screen_leaderboard（排行榜交易者分析）

获取 Hyperliquid 排行榜前 N 名交易者，分析并保存到数据库。

**参数配置**（修改 conf 文件中的 command 参数）:
- `--limit N`: 获取前 N 名交易者（默认: 5000）
- `--workers N`: 并发数/线程数（默认: 1）
- `--proxy`: 启用代理
- `--delay N`: API调用间隔秒数（默认: 1.5）
- `--resume N`: 从第 N 个地址开始（断点续传）

### refresh_stale_traders（过期数据刷新）

刷新数据库中分析时间超过指定小时数的交易者数据。

**参数配置**（修改 conf 文件中的 command 参数）:
- `--hours N`: 超过多少小时视为过期（默认: 12）
- `--rating R`: 最低评级筛选（S/A/B/C/D/F）
- `--limit N`: 限制处理数量（默认: 0=不限制）
- `--workers N`: 并发数/线程数（默认: 1）
- `--proxy`: 启用代理
- `--delay N`: API调用间隔秒数（默认: 1.5）
- `--resume N`: 从第 N 个地址开始（断点续传）

> **注意**: 这两个任务默认不自动启动（`autostart=false`），需要手动启动或通过定时任务触发。

## 部署配置

```bash
# 复制配置文件到 supervisor 目录
sudo cp /www/ai-trading/deploy/supervisor/*.conf /etc/supervisord.d/

# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update
```

## 常用命令

### 启动服务

```bash
# 启动单个服务
sudo supervisorctl start position_copy_trading
sudo supervisorctl start api_server
sudo supervisorctl start monitor_positions

# 启动批量分析任务（按需手动启动）
sudo supervisorctl start screen_leaderboard
sudo supervisorctl start refresh_stale_traders

# 启动所有服务
sudo supervisorctl start all
```

### 停止服务

```bash
# 停止单个服务
sudo supervisorctl stop position_copy_trading
sudo supervisorctl stop api_server
sudo supervisorctl stop monitor_positions
sudo supervisorctl stop screen_leaderboard
sudo supervisorctl stop refresh_stale_traders

# 停止所有服务
sudo supervisorctl stop all
```

### 重启服务

```bash
# 重启单个服务
sudo supervisorctl restart position_copy_trading
sudo supervisorctl restart api_server
sudo supervisorctl restart monitor_positions

# 重启所有服务
sudo supervisorctl restart all
```

### 查看状态

```bash
# 查看所有服务状态
sudo supervisorctl status

# 查看单个服务状态
sudo supervisorctl status position_copy_trading
```

### 查看实时日志

```bash
# 查看 stdout 日志（实时跟踪）
sudo tail -f /www/ai-trading/logs/supervisor_position_copy_trading.log
sudo tail -f /www/ai-trading/logs/supervisor_api_server.log
sudo tail -f /www/ai-trading/logs/supervisor_monitor_positions.log

# 查看 stderr 错误日志
sudo tail -f /www/ai-trading/logs/supervisor_position_copy_trading_error.log
sudo tail -f /www/ai-trading/logs/supervisor_api_server_error.log
sudo tail -f /www/ai-trading/logs/supervisor_monitor_positions_error.log

# 查看最近 100 行日志
sudo tail -n 100 /www/ai-trading/logs/supervisor_position_copy_trading.log

# 同时查看多个日志
sudo tail -f /www/ai-trading/logs/supervisor_*.log
```

### 使用 supervisorctl 查看日志

```bash
# 查看 stdout 日志
sudo supervisorctl tail position_copy_trading

# 实时跟踪 stdout 日志
sudo supervisorctl tail -f position_copy_trading

# 查看 stderr 日志
sudo supervisorctl tail position_copy_trading stderr

# 实时跟踪 stderr 日志
sudo supervisorctl tail -f position_copy_trading stderr
```

## 配置重载

```bash
# 重新读取配置（不重启服务）
sudo supervisorctl reread

# 更新配置并重启变化的服务
sudo supervisorctl update

# 重新加载整个 supervisor
sudo supervisorctl reload
```

## 日志文件位置

| 服务 | stdout 日志 | stderr 日志 |
|------|-------------|-------------|
| position_copy_trading | `logs/supervisor_position_copy_trading.log` | `logs/supervisor_position_copy_trading_error.log` |
| api_server | `logs/supervisor_api_server.log` | `logs/supervisor_api_server_error.log` |
| monitor_positions | `logs/supervisor_monitor_positions.log` | `logs/supervisor_monitor_positions_error.log` |
| screen_leaderboard | `logs/supervisor_screen_leaderboard.log` | `logs/supervisor_screen_leaderboard_error.log` |
| refresh_stale_traders | `logs/supervisor_refresh_stale_traders.log` | `logs/supervisor_refresh_stale_traders_error.log` |
