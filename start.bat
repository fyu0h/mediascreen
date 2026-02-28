@echo off
chcp 65001 >nul 2>&1
title 舆情态势感知平台

:: 激活虚拟环境
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

if /i "%1"=="prod" (
    echo 正在以生产模式启动...
    python run_production.py
) else (
    echo 正在以开发模式启动...
    echo 访问地址: http://localhost:5000
    python app.py
)

pause
