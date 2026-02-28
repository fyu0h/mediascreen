@echo off
chcp 65001 >nul 2>&1
title 皇岗边检站全球舆情态势感知平台 - 一键部署
color 0A

echo ====================================================
echo   皇岗边检站全球舆情态势感知平台 - 一键部署脚本
echo ====================================================
echo.

:: ========== 1. 检查 Python ==========
echo [1/5] 检查 Python 环境...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未检测到 Python，请先安装 Python 3.10 或更高版本
    echo        下载地址: https://www.python.org/downloads/
    echo        安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo        Python %PYVER% - OK
echo.

:: ========== 2. 检查 MongoDB ==========
echo [2/5] 检查 MongoDB...
mongod --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [警告] 未检测到 MongoDB，请确保 MongoDB 已安装并正在运行
    echo        下载地址: https://www.mongodb.com/try/download/community
    echo        如果 MongoDB 已在运行但未加入 PATH，可忽略此警告
    echo.
    set /p CONTINUE="是否继续部署？(Y/N): "
    if /i not "!CONTINUE!"=="Y" if /i not "%CONTINUE%"=="Y" (
        exit /b 1
    )
) else (
    echo        MongoDB - OK
)
echo.

:: ========== 3. 创建虚拟环境 ==========
echo [3/5] 创建 Python 虚拟环境...
if not exist "venv" (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [错误] 创建虚拟环境失败
        pause
        exit /b 1
    )
    echo        虚拟环境创建成功
) else (
    echo        虚拟环境已存在，跳过
)
echo.

:: ========== 4. 安装依赖 ==========
echo [4/5] 安装项目依赖（首次安装可能需要几分钟）...
call venv\Scripts\activate.bat
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败，请检查网络连接
    pause
    exit /b 1
)
echo        依赖安装完成
echo.

:: ========== 5. 初始化配置 ==========
echo [5/5] 初始化配置文件...
if not exist "settings.json" (
    copy settings.example.json settings.json >nul
    echo        已从模板创建 settings.json
    echo        请在 Web 界面的"系统设置"中配置 LLM API 密钥
) else (
    echo        settings.json 已存在，跳过
)
echo.

:: ========== 部署完成 ==========
echo ====================================================
echo   部署完成！
echo ====================================================
echo.
echo   启动方式:
echo     开发模式:  start.bat
echo     生产模式:  start.bat prod
echo.
echo   默认账号: admin / admin123
echo   访问地址: http://localhost:5000
echo.
echo   首次使用请在 Web 界面 "系统设置" 中配置:
echo     - LLM API 密钥（用于翻译和舆情分析）
echo     - 爬虫参数（可选）
echo     - Telegram 监控（可选）
echo ====================================================
echo.
pause
