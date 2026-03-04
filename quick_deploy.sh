#!/bin/bash

# 快速部署脚本

echo "开始快速部署..."

# 拉取最新代码
echo "[1/5] 拉取最新代码..."
git pull origin main

# 查找并停止进程
echo "[2/5] 停止旧进程..."
PID=$(ps aux | grep "[p]ython.*app.py\|[p]ython.*run_production.py" | awk '{print $2}')
if [ -n "$PID" ]; then
    echo "停止进程: $PID"
    kill -9 $PID
    sleep 1
else
    echo "未找到运行中的进程"
fi

# 重新启动
echo "[3/5] 启动应用..."
nohup python run_production.py > logs/production.log 2>&1 &
NEW_PID=$!
echo "应用已启动，PID: $NEW_PID"

# 等待应用启动
echo "[4/5] 等待应用启动..."
sleep 5

# 初始化事件数据（如果数据库为空）
echo "[5/5] 检查事件数据..."
python << 'PYEOF'
from models.events import get_events_count
from services.events_service import get_events_service

count = get_events_count()
print(f"当前事件数量: {count}")

if count == 0:
    print("数据库为空，开始初始化事件数据...")
    service = get_events_service()
    try:
        service._fetch_and_cache_events()
        new_count = get_events_count()
        print(f"✓ 初始化完成，获取了 {new_count} 个事件")
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
else:
    print("✓ 事件数据已存在")
PYEOF

echo ""
echo "=========================================="
echo "部署完成！"
echo "查看日志: tail -f logs/production.log"
echo "=========================================="
