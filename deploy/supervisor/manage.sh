#!/bin/bash
# 跟单机器人管理脚本

PROGRAM="copy_trading"
PROJECT_DIR="/www/ai-trading"
LOG_FILE="$PROJECT_DIR/logs/supervisor_copy_trading.log"

case "$1" in
    start)
        echo "启动 $PROGRAM..."
        sudo supervisorctl start $PROGRAM
        ;;
    stop)
        echo "停止 $PROGRAM..."
        sudo supervisorctl stop $PROGRAM
        ;;
    restart)
        echo "重启 $PROGRAM..."
        sudo supervisorctl restart $PROGRAM
        ;;
    status)
        sudo supervisorctl status $PROGRAM
        ;;
    log)
        tail -f "$LOG_FILE"
        ;;
    log-error)
        tail -f "$PROJECT_DIR/logs/supervisor_copy_trading_error.log"
        ;;
    log-100)
        tail -100 "$LOG_FILE"
        ;;
    reload)
        echo "重新加载配置..."
        sudo supervisorctl reread
        sudo supervisorctl update
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|log|log-error|log-100|reload}"
        echo ""
        echo "命令说明:"
        echo "  start     - 启动跟单机器人"
        echo "  stop      - 停止跟单机器人"
        echo "  restart   - 重启跟单机器人"
        echo "  status    - 查看运行状态"
        echo "  log       - 实时查看日志"
        echo "  log-error - 实时查看错误日志"
        echo "  log-100   - 查看最近100行日志"
        echo "  reload    - 重新加载 Supervisor 配置"
        exit 1
        ;;
esac
