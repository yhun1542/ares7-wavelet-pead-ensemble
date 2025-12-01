#!/usr/bin/env bash
# install_ibgateway.sh
#
# ============================================================================
# IB Gateway Headless Installation Script
# ============================================================================
#
# 역할:
#   - EC2에 IB Gateway 설치 (headless 모드)
#   - Xvfb (가상 디스플레이) 설정
#   - IB Gateway 자동 실행
#
# 실행:
#   chmod +x install_ibgateway.sh
#   ./install_ibgateway.sh
#
# ============================================================================

set -euo pipefail

echo "================================================================================"
echo "IB Gateway Headless Installation"
echo "================================================================================"

# ============================================================================
# 1. Install dependencies
# ============================================================================

echo ""
echo "[1/5] Installing dependencies..."
echo "================================================================================"

sudo apt-get update -qq
sudo apt-get install -y -qq \
    xvfb \
    libxtst6 \
    libxrender1 \
    libxi6 \
    x11vnc \
    socat \
    unzip \
    wget

echo "✅ Dependencies installed"

# ============================================================================
# 2. Install Java (if not installed)
# ============================================================================

echo ""
echo "[2/5] Checking Java..."
echo "================================================================================"

if ! command -v java &> /dev/null; then
    echo "Installing Java..."
    sudo apt-get install -y -qq default-jre
else
    echo "✅ Java already installed"
fi

java -version

# ============================================================================
# 3. Download IB Gateway
# ============================================================================

echo ""
echo "[3/5] Downloading IB Gateway..."
echo "================================================================================"

IBGATEWAY_VERSION="10.19"
IBGATEWAY_INSTALLER="ibgateway-${IBGATEWAY_VERSION}-standalone-linux-x64.sh"
IBGATEWAY_URL="https://download2.interactivebrokers.com/installers/ibgateway/stable-standalone/${IBGATEWAY_INSTALLER}"

cd /tmp

if [ ! -f "${IBGATEWAY_INSTALLER}" ]; then
    echo "Downloading from ${IBGATEWAY_URL}..."
    wget -q "${IBGATEWAY_URL}" || {
        echo "❌ Download failed. Trying alternative version..."
        # Try latest version
        IBGATEWAY_VERSION="latest"
        IBGATEWAY_INSTALLER="ibgateway-latest-standalone-linux-x64.sh"
        IBGATEWAY_URL="https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/${IBGATEWAY_INSTALLER}"
        wget -q "${IBGATEWAY_URL}"
    }
else
    echo "✅ Installer already downloaded"
fi

chmod +x "${IBGATEWAY_INSTALLER}"

# ============================================================================
# 4. Install IB Gateway
# ============================================================================

echo ""
echo "[4/5] Installing IB Gateway..."
echo "================================================================================"

INSTALL_DIR="/opt/ibgateway"

if [ ! -d "${INSTALL_DIR}" ]; then
    echo "Installing to ${INSTALL_DIR}..."
    sudo "./${IBGATEWAY_INSTALLER}" -q -dir "${INSTALL_DIR}"
    echo "✅ IB Gateway installed"
else
    echo "✅ IB Gateway already installed at ${INSTALL_DIR}"
fi

# ============================================================================
# 5. Create configuration files
# ============================================================================

echo ""
echo "[5/5] Creating configuration files..."
echo "================================================================================"

# Create jts.ini for auto-login
mkdir -p ~/Jts

cat > ~/Jts/jts.ini << 'EOF'
[IBGateway]
ApiOnly=true
WriteDebug=true
TrustedIPs=127.0.0.1
LocalServerPort=4001
EOF

echo "✅ Configuration created: ~/Jts/jts.ini"

# ============================================================================
# Done
# ============================================================================

echo ""
echo "================================================================================"
echo "✅ IB Gateway Installation Complete!"
echo "================================================================================"
echo ""
echo "Installation directory: ${INSTALL_DIR}"
echo "Configuration: ~/Jts/jts.ini"
echo ""
echo "Next steps:"
echo "1. Run: ./start_ibgateway.sh"
echo "2. Login with your IBKR credentials"
echo "3. Test connection: python3 ibkr_connect.py"
echo ""
echo "================================================================================"
