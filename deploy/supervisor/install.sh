#!/bin/bash
# Supervisor 安装和配置脚本

set -e

# 配置变量 - 请根据实际情况修改
PROJECT_DIR="/www/ai-trading"
USER="root"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Supervisor 安装配置脚本 ===${NC}"

# 1. 安装 Supervisor
echo -e "${YELLOW}[1/5] 安装 Supervisor...${NC}"
if command -v apt-get &> /dev/null; then
    sudo apt-get update
    sudo apt-get install -y supervisor
elif command -v yum &> /dev/null; then
    sudo yum install -y supervisor
elif command -v dnf &> /dev/null; then
    sudo dnf install -y supervisor
else
    echo -e "${RED}无法识别包管理器，请手动安装 supervisor${NC}"
    exit 1
fi


# 3. 创建日志目录
echo -e "${YELLOW}[3/5] 创建日志目录...${NC}"
mkdir -p "$PROJECT_DIR/logs"
mkdir -p "$PROJECT_DIR/data"
chown -R $USER:$USER "$PROJECT_DIR/logs"
chown -R $USER:$USER "$PROJECT_DIR/data"

# 4. 配置 Supervisor
echo -e "${YELLOW}[4/5] 配置 Supervisor...${NC}"

# Conda 路径配置
CONDA_PYTHON="/root/miniconda3/bin/python"

# 生成配置文件
cat > /tmp/copy_trading.conf << EOF
[program:copy_trading]
command=$CONDA_PYTHON $PROJECT_DIR/examples/copy_trading_example.py
directory=$PROJECT_DIR
user=$USER
environment=PYTHONUNBUFFERED="1"
autostart=true
autorestart=true
startsecs=10
startretries=3
stopwaitsecs=30
stopsignal=SIGTERM
stdout_logfile=$PROJECT_DIR/logs/supervisor_copy_trading.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
stderr_logfile=$PROJECT_DIR/logs/supervisor_copy_trading_error.log
stderr_logfile_maxbytes=50MB
stderr_logfile_backups=10
priority=100
EOF

cat > /tmp/api_server.conf << EOF
[program:api_server]
command=$CONDA_PYTHON $PROJECT_DIR/api_server.py
directory=$PROJECT_DIR
user=$USER
environment=PYTHONUNBUFFERED="1"
autostart=true
autorestart=true
startsecs=10
startretries=3
stopwaitsecs=30
stopsignal=SIGTERM
stdout_logfile=$PROJECT_DIR/logs/supervisor_api_server.log
stdout_logfile_maxbytes=50MB
stdout_logfile_backups=10
stderr_logfile=$PROJECT_DIR/logs/supervisor_api_server_error.log
stderr_logfile_maxbytes=50MB
stderr_logfile_backups=10
priority=90
EOF

# 复制配置到 Supervisor 目录
sudo cp /www/ai-trading/deploy/supervisor/copy_trading.conf /etc/supervisord.d/copy_trading.ini
sudo cp /www/ai-trading/deploy/supervisor/api_server.conf /etc/supervisord.d/api_server.ini

# 5. 启动服务
echo -e "${YELLOW}[5/5] 启动服务...${NC}"
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start api_server
sudo supervisorctl start copy_trading

echo -e "${GREEN}=== 安装完成! ===${NC}"
echo ""
echo "常用命令:"
echo "  查看所有状态: sudo supervisorctl status"
echo ""
echo "  API Server:"
echo "    启动:     sudo supervisorctl start api_server"
echo "    停止:     sudo supervisorctl stop api_server"
echo "    重启:     sudo supervisorctl restart api_server"
echo "    查看日志: tail -f $PROJECT_DIR/logs/supervisor_api_server.log"
echo ""
echo "  Copy Trading:"
echo "    启动:     sudo supervisorctl start copy_trading"
echo "    停止:     sudo supervisorctl stop copy_trading"
echo "    重启:     sudo supervisorctl restart copy_trading"
echo "    查看日志: tail -f $PROJECT_DIR/logs/supervisor_copy_trading.log"
