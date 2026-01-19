# Supervisor 服务管理

## 服务列表

| 服务名 | 说明 | 优先级 |
|--------|------|--------|
| `api_server` | API 服务器 | 90 |
| `position_copy_trading` | 仓位级别跟单机器人 | 100 |
| `monitor_positions` | S级交易员仓位监控 | 110 |

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

# 启动所有服务
sudo supervisorctl start all
```

### 停止服务

```bash
# 停止单个服务
sudo supervisorctl stop position_copy_trading
sudo supervisorctl stop api_server
sudo supervisorctl stop monitor_positions

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
