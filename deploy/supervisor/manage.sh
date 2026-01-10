#!/bin/bash
# 服务管理脚本 - 支持 api_server 和 copy_trading

PROJECT_DIR="/www/ai-trading"

# 默认程序为 copy_trading，可通过第二个参数指定
PROGRAM="${2:-all}"

get_log_file() {
    case "$1" in
        api_server)
            echo "$PROJECT_DIR/logs/supervisor_api_server.log"
            ;;
        copy_trading)
            echo "$PROJECT_DIR/logs/supervisor_copy_trading.log"
            ;;
    esac
}

get_error_log_file() {
    case "$1" in
        api_server)
            echo "$PROJECT_DIR/logs/supervisor_api_server_error.log"
            ;;
        copy_trading)
            echo "$PROJECT_DIR/logs/supervisor_copy_trading_error.log"
            ;;
    esac
}

case "$1" in
    start)
        if [ "$PROGRAM" = "all" ]; then
            echo "启动所有服务..."
            sudo supervisorctl start api_server
            sudo supervisorctl start copy_trading
        else
            echo "启动 $PROGRAM..."
            sudo supervisorctl start $PROGRAM
        fi
        ;;
    stop)
        if [ "$PROGRAM" = "all" ]; then
            echo "停止所有服务..."
            sudo supervisorctl stop copy_trading
            sudo supervisorctl stop api_server
        else
            echo "停止 $PROGRAM..."
            sudo supervisorctl stop $PROGRAM
        fi
        ;;
    restart)
        if [ "$PROGRAM" = "all" ]; then
            echo "重启所有服务..."
            sudo supervisorctl restart api_server
            sudo supervisorctl restart copy_trading
        else
            echo "重启 $PROGRAM..."
            sudo supervisorctl restart $PROGRAM
        fi
        ;;
    status)
        if [ "$PROGRAM" = "all" ]; then
            sudo supervisorctl status
        else
            sudo supervisorctl status $PROGRAM
        fi
        ;;
    log)
        if [ "$PROGRAM" = "all" ]; then
            echo "请指定服务名: $0 log api_server 或 $0 log copy_trading"
            exit 1
        fi
        LOG_FILE=$(get_log_file $PROGRAM)
        tail -f "$LOG_FILE"
        ;;
    log-error)
        if [ "$PROGRAM" = "all" ]; then
            echo "请指定服务名: $0 log-error api_server 或 $0 log-error copy_trading"
            exit 1
        fi
        ERROR_LOG=$(get_error_log_file $PROGRAM)
        tail -f "$ERROR_LOG"
        ;;
    log-100)
        if [ "$PROGRAM" = "all" ]; then
            echo "请指定服务名: $0 log-100 api_server 或 $0 log-100 copy_trading"
            exit 1
        fi
        LOG_FILE=$(get_log_file $PROGRAM)
        tail -100 "$LOG_FILE"
        ;;
    reload)
        echo "重新加载配置..."
        sudo supervisorctl reread
        sudo supervisorctl update
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status|log|log-error|log-100|reload} [服务名]"
        echo ""
        echo "服务名 (可选):"
        echo "  api_server    - API 服务器 (端口 5000)"
        echo "  copy_trading  - 跟单机器人"
        echo "  all           - 所有服务 (默认)"
        echo ""
        echo "命令说明:"
        echo "  start     - 启动服务"
        echo "  stop      - 停止服务"
        echo "  restart   - 重启服务"
        echo "  status    - 查看运行状态"
        echo "  log       - 实时查看日志 (需指定服务名)"
        echo "  log-error - 实时查看错误日志 (需指定服务名)"
        echo "  log-100   - 查看最近100行日志 (需指定服务名)"
        echo "  reload    - 重新加载 Supervisor 配置"
        echo ""
        echo "示例:"
        echo "  $0 start                 - 启动所有服务"
        echo "  $0 start api_server      - 仅启动 API 服务器"
        echo "  $0 restart copy_trading  - 重启跟单机器人"
        echo "  $0 log api_server        - 查看 API 服务器日志"
        echo "  $0 status                - 查看所有服务状态"
        exit 1
        ;;
esac
