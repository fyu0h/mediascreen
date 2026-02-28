#!/bin/bash
# 皇岗边检站全球舆情态势感知平台 - 启动脚本 (Linux)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 激活虚拟环境
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

if [ "$1" = "prod" ]; then
    echo "正在以生产模式启动..."
    python run_production.py
else
    echo "正在以开发模式启动..."
    echo "访问地址: http://localhost:5000"
    python app.py
fi
