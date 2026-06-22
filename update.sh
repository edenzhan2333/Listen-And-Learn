#!/bin/bash
# ============================================================
# Listen and Learn —— 一键更新脚本
# 同步本地代码到服务器并重启服务（不重新安装依赖）
# 在本地 Mac 终端执行
# ============================================================

set -e

SERVER_IP="49.232.226.131"
SSH_PORT="22"
SSH_USER="root"
SSH_PASS="EdenZhan2333"
REMOTE_DIR="/opt/listenandlearn"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

info "=== Listen and Learn 一键更新 ==="

# 检查 sshpass
USE_SSHPASS=false
if command -v sshpass &> /dev/null; then
    USE_SSHPASS=true
fi

# SSH/SCP 命令封装
if [ "$USE_SSHPASS" = true ]; then
    SSH_BASE="sshpass -p ${SSH_PASS} ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no ${SSH_USER}@${SERVER_IP}"
    RSYNC_BASE="sshpass -p ${SSH_PASS} rsync -avz -e ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no"
else
    SSH_BASE="ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no ${SSH_USER}@${SERVER_IP}"
    RSYNC_BASE="rsync -avz -e ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no"
fi

# ===== Step 1: 同步代码 =====
info "Step 1: 同步代码到服务器（排除数据/虚拟环境/配置文件）"

if [ "$USE_SSHPASS" = true ]; then
    sshpass -p "${SSH_PASS}" rsync -avz \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='data/' \
        --exclude='.env' \
        --exclude='venv/' \
        --exclude='tests/' \
        --exclude='pyrightconfig.json' \
        --exclude='pyproject.toml' \
        -e "ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no" \
        "$(dirname "$0")/backend/" \
        "${SSH_USER}@${SERVER_IP}:${REMOTE_DIR}/"
else
    echo ""
    warn "未安装 sshpass，将使用交互式同步（需要输入服务器密码：${SSH_PASS}）"
    echo ""
    rsync -avz \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='data/' \
        --exclude='.env' \
        --exclude='venv/' \
        --exclude='tests/' \
        --exclude='pyrightconfig.json' \
        --exclude='pyproject.toml' \
        -e "ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no" \
        "$(dirname "$0")/backend/" \
        "${SSH_USER}@${SERVER_IP}:${REMOTE_DIR}/"
fi

info "代码同步完成"

# ===== Step 2: 更新 .env 环境变量 =====
info "Step 2: 更新 .env 环境变量"

if [ "$USE_SSHPASS" = true ]; then
    sshpass -p "${SSH_PASS}" ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no ${SSH_USER}@${SERVER_IP} 'bash -s' << 'ENVEOF'
cat > /opt/listenandlearn/.env << 'EOF'
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
echo "[INFO] .env 已更新"
ENVEOF
else
    echo ""
    warn "未安装 sshpass，将使用交互式 SSH（需要输入密码：${SSH_PASS}）"
    echo ""
    ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no ${SSH_USER}@${SERVER_IP} 'bash -s' << 'ENVEOF'
cat > /opt/listenandlearn/.env << 'EOF'
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
echo "[INFO] .env 已更新"
ENVEOF
fi

# ===== Step 3: 重启服务 =====
info "Step 3: 重启服务"

if [ "$USE_SSHPASS" = true ]; then
    sshpass -p "${SSH_PASS}" ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no ${SSH_USER}@${SERVER_IP} 'bash -s' << 'REMOTE_SCRIPT'
set -e
echo "[INFO] 停止服务..."
systemctl stop listenandlearn
sleep 1

echo "[INFO] 清理 Python 缓存..."
find /opt/listenandlearn/app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find /opt/listenandlearn/app -name "*.pyc" -delete 2>/dev/null || true

echo "[INFO] 启动服务..."
systemctl start listenandlearn
sleep 3

echo "[INFO] 检查服务状态..."
if systemctl is-active --quiet listenandlearn; then
    echo "[SUCCESS] 服务已重启并运行中"
else
    echo "[ERROR] 服务启动失败，查看日志:"
    journalctl -u listenandlearn -n 30 --no-pager
    exit 1
fi

echo "[INFO] 健康检查..."
curl -s http://localhost:8000/api/health && echo ""
echo "[DONE]"
REMOTE_SCRIPT
else
    echo ""
    warn "未安装 sshpass，将使用交互式 SSH（需要再次输入密码：${SSH_PASS}）"
    echo ""
    ssh -p ${SSH_PORT} -o StrictHostKeyChecking=no ${SSH_USER}@${SERVER_IP} 'bash -s' << 'REMOTE_SCRIPT'
set -e
echo "[INFO] 停止服务..."
systemctl stop listenandlearn
sleep 1

echo "[INFO] 清理 Python 缓存..."
find /opt/listenandlearn/app -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find /opt/listenandlearn/app -name "*.pyc" -delete 2>/dev/null || true

echo "[INFO] 启动服务..."
systemctl start listenandlearn
sleep 3

echo "[INFO] 检查服务状态..."
if systemctl is-active --quiet listenandlearn; then
    echo "[SUCCESS] 服务已重启并运行中"
else
    echo "[ERROR] 服务启动失败，查看日志:"
    journalctl -u listenandlearn -n 30 --no-pager
    exit 1
fi

echo "[INFO] 健康检查..."
curl -s http://localhost:8000/api/health && echo ""
echo "[DONE]"
REMOTE_SCRIPT
fi

# ===== Step 4: 完成 =====
echo ""
info "=== 更新完成 ==="
echo "后端服务地址: http://${SERVER_IP}:8000"
