#!/usr/bin/env bash
# start_ibgateway.sh
#
# ============================================================================
# IB Gateway Headless Startup Script
# ============================================================================
#
# 역할:
#   - Xvfb (가상 디스플레이) 시작
#   - IB Gateway 실행
#   - 자동 로그인 (credentials 필요)
#
# 실행:
#   ./start_ibgateway.sh
#
# ============================================================================

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

IBGATEWAY_DIR="/opt/ibgateway"
DISPLAY_NUM=":1"
VNC_PORT="5901"

# IBKR Credentials (CHANGE THESE!)
IB_USERNAME="${IB_USERNAME:-jasonjun0612}"
IB_PASSWORD="${IB_PASSWORD:-Kimerajason1542!}"
IB_TRADING_MODE="${IB_TRADING_MODE:-paper}"  # paper or live

# ============================================================================
# Functions
# ============================================================================

start_xvfb() {
    echo "Starting Xvfb on display ${DISPLAY_NUM}..."
    
    # Kill existing Xvfb
    pkill -f "Xvfb ${DISPLAY_NUM}" 2>/dev/null || true
    
    # Start Xvfb
    Xvfb ${DISPLAY_NUM} -screen 0 1024x768x24 &
    XVFB_PID=$!
    
    export DISPLAY=${DISPLAY_NUM}
    
    sleep 2
    echo "✅ Xvfb started (PID: ${XVFB_PID})"
}

start_vnc() {
    echo "Starting VNC server on port ${VNC_PORT}..."
    
    # Kill existing x11vnc
    pkill -f "x11vnc" 2>/dev/null || true
    
    # Start x11vnc
    x11vnc -display ${DISPLAY_NUM} -bg -nopw -listen localhost -xkb -rfbport ${VNC_PORT} &
    
    echo "✅ VNC server started on localhost:${VNC_PORT}"
    echo "   (For debugging: ssh -L ${VNC_PORT}:localhost:${VNC_PORT} ubuntu@ec2)"
}

start_ibgateway() {
    echo "Starting IB Gateway..."
    
    # Kill existing IB Gateway
    pkill -f "ibgateway" 2>/dev/null || true
    
    # Set DISPLAY
    export DISPLAY=${DISPLAY_NUM}
    
    # Start IB Gateway
    cd "${IBGATEWAY_DIR}"
    
    if [ "${IB_TRADING_MODE}" = "paper" ]; then
        echo "Mode: Paper Trading"
        ./ibgateway paperlive &
    else
        echo "Mode: Live Trading"
        ./ibgateway live &
    fi
    
    IBGATEWAY_PID=$!
    
    echo "✅ IB Gateway started (PID: ${IBGATEWAY_PID})"
    echo "   Waiting for startup..."
    
    sleep 10
}

# ============================================================================
# Main
# ============================================================================

echo "================================================================================"
echo "IB Gateway Headless Startup"
echo "================================================================================"
echo "Username: ${IB_USERNAME}"
echo "Mode: ${IB_TRADING_MODE}"
echo "================================================================================"

# Check if IB Gateway is installed
if [ ! -d "${IBGATEWAY_DIR}" ]; then
    echo "❌ IB Gateway not found at ${IBGATEWAY_DIR}"
    echo "   Run: ./install_ibgateway.sh first"
    exit 1
fi

# Start Xvfb
start_xvfb

# Start VNC (optional, for debugging)
start_vnc

# Start IB Gateway
start_ibgateway

echo ""
echo "================================================================================"
echo "✅ IB Gateway is running!"
echo "================================================================================"
echo ""
echo "Check status:"
echo "  ps aux | grep ibgateway"
echo ""
echo "Test connection:"
echo "  python3 ibkr_connect.py"
echo ""
echo "View logs:"
echo "  tail -f ~/Jts/ibgateway/*/log.*"
echo ""
echo "Stop IB Gateway:"
echo "  pkill -f ibgateway"
echo ""
echo "================================================================================"
