#!/bin/bash
# ============================================================
# Listen and Learn —— 一键部署脚本
# 在本地(macOS)执行，自动部署后端到远程 CentOS 服务器
# ============================================================

set -e

# ===== 配置 =====
SERVER_IP="49.232.226.131"
SSH_PORT="22"
SSH_USER="root"
SSH_PASS="EdenZhan2333"
REMOTE_DIR="/opt/listenandlearn"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

info "=== Listen and Learn 一键部署 ==="

# ===== 前置检查 =====
if ! command -v sshpass &> /dev/null; then
    warn "sshpass 未安装，正在安装..."
    brew install hudochenkov/sshpass/sshpass 2>/dev/null || {
        error "无法安装 sshpass，请手动安装: brew install hudochenkov/sshpass/sshpass"
        exit 1
    }
fi

if ! command -v rsync &> /dev/null; then
    error "rsync 未安装，请先安装"
    exit 1
fi

SSH_CMD="sshpass -p '${SSH_PASS}' ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no ${SSH_USER}@${SERVER_IP}"

# ===== Step 1: 同步代码 =====
info "Step 1: 同步代码到服务器 ${SERVER_IP}:${REMOTE_DIR}"
eval ${SSH_CMD} "mkdir -p ${REMOTE_DIR}"

eval sshpass -p \'${SSH_PASS}\' rsync -avz --progress \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='data/' \
    --exclude='.env' \
    --exclude='venv/' \
    --exclude='tests/' \
    --exclude='pyrightconfig.json' \
    --exclude='pyproject.toml' \
    -e \"ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no\" \
    "$(dirname "$0")/backend/" \
    "${SSH_USER}@${SERVER_IP}:${REMOTE_DIR}/"

info "代码同步完成"

# ===== Step 2: 远程安装环境 (CentOS/yum) =====
info "Step 2: 远程安装 Python 环境和系统依赖 (CentOS)"

eval ${SSH_CMD} 'bash -s' << 'REMOTE_SCRIPT'
set -e
REMOTE_DIR="/opt/listenandlearn"

# ===== 检测包管理器 =====
if command -v dnf &> /dev/null; then
    PKG_MGR="dnf"
elif command -v yum &> /dev/null; then
    PKG_MGR="yum"
else
    echo "[ERROR] 未找到 dnf 或 yum，无法继续"
    exit 1
fi
echo "[INFO] 包管理器: $PKG_MGR"

# ===== 安装 EPEL 仓库 =====
echo "[INFO] 安装 EPEL 仓库..."
$PKG_MGR install -y epel-release 2>/dev/null || echo "[WARN] EPEL 可能已安装"

# ===== 安装 RPMFusion 仓库 (用于 ffmpeg) =====
echo "[INFO] 安装 RPMFusion 仓库 (用于 ffmpeg)..."
if [ -f /etc/redhat-release ]; then
    if grep -q "release 8" /etc/redhat-release; then
        $PKG_MGR install -y https://mirrors.aliyun.com/rpmfusion/free/el/8/x86_64/r/rpmfusion-free-release-8.noarch.rpm 2>/dev/null || true
    elif grep -q "release 9" /etc/redhat-release; then
        $PKG_MGR install -y https://mirrors.aliyun.com/rpmfusion/free/el/9/x86_64/r/rpmfusion-free-release-9.noarch.rpm 2>/dev/null || true
    elif grep -q "release 7" /etc/redhat-release; then
        $PKG_MGR localinstall -y https://mirrors.aliyun.com/rpmfusion/free/el/7/x86_64/r/rpmfusion-free-release-7.noarch.rpm 2>/dev/null || true
    fi
fi

# ===== 安装系统依赖 =====
echo "[INFO] 安装系统依赖..."
$PKG_MGR install -y python3 python3-pip python3-devel gcc ffmpeg curl

# 验证 Python
PYTHON_BIN="python3"
echo "[INFO] Python: $($PYTHON_BIN --version)"

# 验证 ffmpeg
if command -v ffmpeg &> /dev/null; then
    echo "[INFO] ffmpeg: $(ffmpeg -version | head -1)"
else
    echo "[WARN] ffmpeg 未安装成功，音频拼接将回退到 pydub"
fi

# ===== 创建虚拟环境 =====
echo "[INFO] 创建虚拟环境..."
cd $REMOTE_DIR
$PYTHON_BIN -m venv venv

# ===== 安装 Python 依赖 =====
echo "[INFO] 安装 Python 依赖..."
./venv/bin/pip install --upgrade pip -q
./venv/bin/pip install -r requirements.txt -q
echo "[INFO] Python 依赖安装完成"

# ===== 写入环境变量 =====
echo "[INFO] 写入环境变量..."
cat > $REMOTE_DIR/.env << 'EOF'
DASHSCOPE_API_KEY=sk-ws-H.RPRPYYI.UVUB.MEUCIC6Fh7TGirqbgzz7AbELtuRxz2r8lFQ_ZWSh_KUEjnyYAiEAxdM0x4UNuqJvHM4BdRydg7NmRF-Bt4QrxyiBUFFabgM
TTS_MODEL=cosyvoice-v3-plus
MALE_VOICE=longanyang
FEMALE_VOICE=longanhuan
ZAI_API_KEY=82e775bb5a104459826a64822b03483e.UoHJo9vVhYsdWtQ7
ZAI_MODEL=glm-5.2
ZAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
HOST=0.0.0.0
PORT=8000
DATA_DIR=/opt/listenandlearn/data
EOF
echo "[INFO] .env 文件已创建"

mkdir -p $REMOTE_DIR/data/knowledge_base
mkdir -p $REMOTE_DIR/data/podcasts
mkdir -p $REMOTE_DIR/data/news

# ===== 创建 systemd 服务 =====
echo "[INFO] 创建 systemd 服务..."
cat > /etc/systemd/system/listenandlearn.service << EOF
[Unit]
Description=Listen and Learn Backend
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${REMOTE_DIR}
EnvironmentFile=${REMOTE_DIR}/.env
ExecStart=${REMOTE_DIR}/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# ===== 启动服务 =====
echo "[INFO] 启动服务..."
systemctl daemon-reload
systemctl enable listenandlearn
systemctl restart listenandlearn

echo "[INFO] 等待服务启动..."
sleep 4

echo "[INFO] 检查服务状态..."
if systemctl is-active --quiet listenandlearn; then
    echo "[SUCCESS] 服务已启动并运行中"
else
    echo "[ERROR] 服务启动失败，查看日志:"
    journalctl -u listenandlearn -n 30 --no-pager
    exit 1
fi

echo "[INFO] 健康检查..."
curl -s http://localhost:8000/api/health || echo "[WARN] 健康检查未通过，服务可能仍在启动中"

echo "[DONE]"
REMOTE_SCRIPT

# ===== Step 3: 验证部署 =====
info "Step 3: 验证部署"
eval ${SSH_CMD} "curl -s http://localhost:8000/api/health"

echo ""
info "=== 部署完成 ==="
echo ""
echo "后端服务地址: http://${SERVER_IP}:8000"
echo "API 文档:     http://${SERVER_IP}:8000/docs"
echo "健康检查:     http://${SERVER_IP}:8000/api/health"
echo ""
echo "在安卓客户端中输入后端地址: ${SERVER_IP}:8000"
echo ""
