#!/bin/bash

# 态势感知平台部署脚本

set -e  # 遇到错误立即退出

echo "=========================================="
echo "开始部署态势感知平台"
echo "=========================================="

# 项目目录（根据实际情况修改）
PROJECT_DIR="/path/to/态势感知"
cd "$PROJECT_DIR"

# 1. 备份当前版本
echo "[1/6] 备份当前版本..."
BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r . "$BACKUP_DIR/" 2>/dev/null || true
echo "备份完成: $BACKUP_DIR"

# 2. 拉取最新代码
echo "[2/6] 拉取最新代码..."
git fetch origin
git pull origin main
echo "代码更新完成"

# 3. 检查并安装依赖
echo "[3/6] 检查依赖..."
pip install -r requirements.txt --upgrade
echo "依赖安装完成"

# 4. 停止旧进程
echo "[4/6] 停止旧进程..."
# 方式1: 使用 systemd
if systemctl is-active --quiet news-dashboard 2>/dev/null; then
    sudo systemctl stop news-dashboard
    echo "已停止 systemd 服务"
# 方式2: 使用 supervisor
elif supervisorctl status news-dashboard >/dev/null 2>&1; then
    sudo supervisorctl stop news-dashboard
    echo "已停止 supervisor 服务"
# 方式3: 直接杀进程
else
    PID=$(ps aux | grep "[p]ython.*app.py\|[p]ython.*run_production.py" | awk '{print $2}')
    if [ -n "$PID" ]; then
        kill -15 $PID
        sleep 2
        # 如果还没停止，强制杀掉
        if ps -p $PID > /dev/null 2>&1; then
            kill -9 $PID
        fi
        echo "已停止进程: $PID"
    else
        echo "未找到运行中的进程"
    fi
fi

# 5. 启动新进程
echo "[5/6] 启动新进程..."
# 方式1: 使用 systemd
if [ -f /etc/systemd/system/news-dashboard.service ]; then
    sudo systemctl start news-dashboard
    echo "已启动 systemd 服务"
# 方式2: 使用 supervisor
elif [ -f /etc/supervisor/conf.d/news-dashboard.conf ]; then
    sudo supervisorctl start news-dashboard
    echo "已启动 supervisor 服务"
# 方式3: 直接启动
else
    nohup python run_production.py > logs/production.log 2>&1 &
    echo "已启动应用进程"
fi

# 6. 检查服务状态
echo "[6/6] 检查服务状态..."
sleep 3

# 检查进程是否运行
if ps aux | grep -q "[p]ython.*app.py\|[p]ython.*run_production.py"; then
    echo "✓ 应用进程运行正常"
else
    echo "✗ 应用进程未运行，请检查日志"
    exit 1
fi

# 检查端口是否监听
if netstat -tuln | grep -q ":5000" || ss -tuln | grep -q ":5000"; then
    echo "✓ 端口 5000 监听正常"
else
    echo "✗ 端口 5000 未监听，请检查日志"
    exit 1
fi

echo "=========================================="
echo "部署完成！"
echo "访问地址: http://$(hostname -I | awk '{print $1}'):5000"
echo "日志文件: logs/production.log"
echo "=========================================="
