#!/bin/bash

# 快速部署脚本

echo "开始快速部署..."

# 拉取最新代码
git pull origin main

# 查找并停止进程
PID=$(ps aux | grep "[p]ython.*app.py\|[p]ython.*run_production.py" | awk '{print $2}')
if [ -n "$PID" ]; then
    echo "停止进程: $PID"
    kill -9 $PID
fi

# 重新启动
echo "启动应用..."
nohup python run_production.py > logs/production.log 2>&1 &

sleep 2
echo "部署完成！"
echo "查看日志: tail -f logs/production.log"
