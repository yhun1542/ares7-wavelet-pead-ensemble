#!/bin/bash
#
# IBC Headless Start Script
# Starts IB Gateway with IBC in headless mode (no xterm required)
#

set -e

echo "========================================"
echo "Starting IB Gateway with IBC (Headless)"
echo "========================================"

# Kill existing processes
echo "Stopping existing IB Gateway..."
ps aux | grep -E 'ibgateway|GWClient|IBC' | grep -v grep | awk '{print $2}' | xargs sudo kill -9 2>/dev/null || true
sleep 3

# IBC Configuration
export TWS_MAJOR_VRSN=10.19
export IBC_INI=/opt/ibc/config.ini
export IBC_PATH=/opt/ibc
export TWS_PATH=/opt/ibgateway
export TWS_CONFIG_PATH=/root/Jts
export TRADING_MODE=paper
export DISPLAY=:1

# Java options
export JAVA_OPTS="-Xmx768m -XX:+UseG1GC"

# IBC JAR
IBC_JAR=/opt/ibc/IBC.jar

if [ -z "$IBC_JAR" ]; then
    echo "ERROR: IBC JAR not found"
    exit 1
fi

echo "IBC JAR: $IBC_JAR"
echo "IBC INI: $IBC_INI"
echo "Trading Mode: $TRADING_MODE"
echo "Display: $DISPLAY"

# Start IBC
echo "Starting IBC..."
cd /opt/ibc

sudo -E java $JAVA_OPTS \
    -cp "$IBC_JAR:$TWS_PATH/jars/*" \
    ibcalpha.ibc.IbcTws \
    "$IBC_INI" \
    > /tmp/ibc_headless.log 2>&1 &

IBC_PID=$!
echo "IBC started with PID: $IBC_PID"

# Wait for startup
echo "Waiting for IB Gateway to start..."
sleep 15

# Check if running
if ps -p $IBC_PID > /dev/null; then
    echo "✅ IBC is running"
else
    echo "❌ IBC failed to start"
    echo "Check log: /tmp/ibc_headless.log"
    exit 1
fi

# Check for API port
echo "Checking API port 4001..."
sleep 10

if netstat -tuln | grep -q 4001; then
    echo "✅ API port 4001 is listening"
else
    echo "⏳ API port 4001 not yet available (may need IB Key approval)"
fi

echo "========================================"
echo "IBC startup complete"
echo "Log: /tmp/ibc_headless.log"
echo "========================================"
