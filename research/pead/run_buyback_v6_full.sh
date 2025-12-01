#!/bin/bash
# Run Buyback Event Builder v6 for full SP100
# Expected time: 3-8 hours

cd /home/ubuntu/ares7-ensemble
source venv/bin/activate

echo "=================================="
echo "Buyback Event Builder v6 - Full SP100"
echo "Start time: $(date)"
echo "=================================="
echo ""

# Run the extraction
python3 research/pead/buyback_event_builder_v6.py 2>&1 | tee data/buyback/extraction_v6_full.log

echo ""
echo "=================================="
echo "Extraction complete"
echo "End time: $(date)"
echo "=================================="
echo ""

# Show summary
echo "Results:"
wc -l data/buyback/buyback_events_v6.csv
echo ""

echo "Log file: data/buyback/extraction_v6_full.log"
echo "Output file: data/buyback/buyback_events_v6.csv"
