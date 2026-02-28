#!/bin/bash
# 皇岗边检站全球舆情态势感知平台 - 一键部署脚本 (Linux)

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "===================================================="
echo "  皇岗边检站全球舆情态势感知平台 - 一键部署脚本"
echo "===================================================="
echo ""

# 获取脚本所在目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ========== 1. 检查 Python ==========
echo -e "[1/5] 检查 Python 环境..."
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo -e "${RED}[错误] 未检测到 Python，请先安装 Python 3.10+${NC}"
    echo "  Ubuntu/Debian:  sudo apt install python3 python3-venv python3-pip"
    echo "  CentOS/RHEL:    sudo yum install python3 python3-pip"
    exit 1
fi
PYVER=$($PYTHON --version 2>&1)
echo -e "       ${GREEN}${PYVER} - OK${NC}"
echo ""

# ========== 2. 检查 MongoDB ==========
echo "[2/5] 检查 MongoDB..."
if command -v mongod &>/dev/null || systemctl is-active --quiet mongod 2>/dev/null; then
    echo -e "       ${GREEN}MongoDB - OK${NC}"
else
    echo -e "${YELLOW}[警告] 未检测到 MongoDB${NC}"
    echo ""
    read -p "是否自动安装 MongoDB 7.0？(y/N): " INSTALL_MONGO
    if [[ "$INSTALL_MONGO" =~ ^[Yy]$ ]]; then
        echo "       正在安装 MongoDB 7.0 ..."
        # 导入 GPG 密钥
        curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor --yes
        # 检测 Ubuntu 版本，添加对应 apt 源
        UBUNTU_CODENAME=$(lsb_release -cs 2>/dev/null || echo "focal")
        # MongoDB 7.0 官方源仅支持 focal/jammy，其余版本回退 focal
        case "$UBUNTU_CODENAME" in
            focal|jammy) ;;
            *) UBUNTU_CODENAME="focal" ;;
        esac
        echo "deb [ signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu ${UBUNTU_CODENAME}/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list >/dev/null
        sudo apt-get update -qq
        sudo apt-get install -y mongodb-org -qq
        sudo systemctl start mongod
        sudo systemctl enable mongod
        echo -e "       ${GREEN}MongoDB 7.0 安装完成并已启动${NC}"
    else
        echo -e "${YELLOW}       跳过 MongoDB 安装，请确保后续手动安装并启动${NC}"
    fi
fi
echo ""

# ========== 3. 创建虚拟环境 ==========
echo "[3/5] 创建 Python 虚拟环境..."
if [ ! -f "venv/bin/activate" ]; then
    # 目录存在但不完整，先删除
    rm -rf venv 2>/dev/null || true
    # 确保 python3-venv 已安装
    if ! $PYTHON -m venv --help &>/dev/null; then
        echo "       安装 python3-venv ..."
        sudo apt-get install -y python3-venv -qq
    fi
    $PYTHON -m venv venv
    echo -e "       ${GREEN}虚拟环境创建成功${NC}"
else
    echo "       虚拟环境已存在，跳过"
fi
echo ""

# ========== 4. 安装依赖 ==========
echo "[4/5] 安装项目依赖（首次安装可能需要几分钟）..."
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo -e "       ${GREEN}依赖安装完成${NC}"
echo ""

# ========== 5. 初始化配置 ==========
echo "[5/5] 初始化配置文件..."
if [ ! -f "settings.json" ]; then
    cp settings.example.json settings.json
    echo "       已从模板创建 settings.json"
    echo "       请在 Web 界面的「系统设置」中配置 LLM API 密钥"
else
    echo "       settings.json 已存在，跳过"
fi
echo ""

# ========== 设置脚本可执行权限 ==========
chmod +x start.sh 2>/dev/null || true

# ========== 部署完成 ==========
echo "===================================================="
echo -e "  ${GREEN}部署完成！${NC}"
echo "===================================================="
echo ""
echo "  启动方式:"
echo "    开发模式:  ./start.sh"
echo "    生产模式:  ./start.sh prod"
echo "    后台运行:  nohup ./start.sh prod > app.log 2>&1 &"
echo ""
echo "  默认账号: admin / admin123"
echo "  访问地址: http://localhost:5000"
echo ""
echo "  首次使用请在 Web 界面「系统设置」中配置:"
echo "    - LLM API 密钥（用于翻译和舆情分析）"
echo "    - 爬虫参数（可选）"
echo "    - Telegram 监控（可选）"
echo "===================================================="
