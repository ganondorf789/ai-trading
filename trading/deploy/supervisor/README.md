# Trading 模块 Supervisor 服务管理

## 服务列表

| 服务名 | 说明 | 端口 | 优先级 | 自动启动 |
|--------|------|------|--------|----------|
| `trading_app` | Trading API 服务器 | 5001 | 95 | 是 |
| `trading_run_bot` | 仓位级别跟单机器人（gRPC 模式） | - | 105 | 是 |

### trading_app（Trading API 服务器）

独立的交易服务，提供交易操作和日志查询 API，使用 API Key 认证。

- 监听端口: 5001
- 认证方式: `X-API-Key` Header 或 `?api_key=` Query Parameter
- Swagger 文档: `http://<host>:5001/docs`
- 健康检查: `GET /health`（无需认证）

### trading_run_bot（仓位级别跟单机器人）

通过 gRPC 服务访问数据库和 Redis，跟单特定交易员的特定仓位。

- 依赖: gRPC 服务器需先启动（`grpc_server.py`）
- 配置: `trading/.env` 文件
- 支持参数: `--grpc-host`、`--grpc-port`

## 部署配置

```bash
# 复制配置文件到 supervisor 目录
sudo cp /www/ai-trading/trading/deploy/supervisor/*.conf /etc/supervisord.d/

# 重新加载配置
sudo supervisorctl reread
sudo supervisorctl update
```

## 常用命令

### 启动服务

```bash
sudo supervisorctl start trading_app
sudo supervisorctl start trading_run_bot

# 启动全部
sudo supervisorctl start trading_app trading_run_bot
```

### 停止服务

```bash
sudo supervisorctl stop trading_app
sudo supervisorctl stop trading_run_bot

# 停止全部
sudo supervisorctl stop trading_app trading_run_bot
```

### 重启服务

```bash
sudo supervisorctl restart trading_app
sudo supervisorctl restart trading_run_bot

# 重启全部
sudo supervisorctl restart trading_app trading_run_bot
```

### 查看状态

```bash
sudo supervisorctl status trading_app
sudo supervisorctl status trading_run_bot
```

### 查看实时日志

```bash
# trading_app 日志
sudo tail -f /www/ai-trading/logs/supervisor_trading_app.log
sudo tail -f /www/ai-trading/logs/supervisor_trading_app_error.log

# trading_run_bot 日志
sudo tail -f /www/ai-trading/logs/supervisor_trading_run_bot.log
sudo tail -f /www/ai-trading/logs/supervisor_trading_run_bot_error.log
```

## 日志文件位置

| 服务 | stdout 日志 | stderr 日志 |
|------|-------------|-------------|
| trading_app | `logs/supervisor_trading_app.log` | `logs/supervisor_trading_app_error.log` |
| trading_run_bot | `logs/supervisor_trading_run_bot.log` | `logs/supervisor_trading_run_bot_error.log` |
