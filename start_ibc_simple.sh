#!/bin/bash
# Simple IBC Launcher for Paper Trading

echo "Killing all existing IB Gateway processes..."
sudo pkill -9 -f 'ibgateway|GWClient|IBC|java.*install4j' 2>/dev/null
sleep 5

echo "Starting IBC with Paper Trading..."

cd /opt/ibc

sudo DISPLAY=:1 java -Xmx768m -XX:+UseG1GC \
    -cp "/opt/ibc/IBC.jar:/opt/ibgateway/jars/*" \
    ibcalpha.ibc.IbcTws \
    /opt/ibc/config.ini \
    > /tmp/ibc_simple.log 2>&1 &

echo "IBC started. Waiting 60 seconds for login..."
sleep 60

echo "Checking API port 4001..."
if netstat -tuln | grep -q 4001 || ss -tuln | grep -q 4001; then
    echo "✅ SUCCESS! API port 4001 is listening"
    echo "You can now connect to IB Gateway API"
else
    echo "❌ API port 4001 not listening yet"
    echo "Check log: tail -f /tmp/ibc_simple.log"
fi
