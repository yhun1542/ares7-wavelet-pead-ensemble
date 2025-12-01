#!/usr/bin/env python3
"""
Test script for Buyback Event Builder v5
Tests with 5 tickers only: AAPL, MSFT, GOOGL, AMZN, NVDA
"""

import os
import sys

# Temporarily override universe file for testing
os.environ['TEST_MODE'] = '1'

# Import the main script
sys.path.insert(0, '/home/ubuntu/ares7-ensemble/research/pead')

# Modify constants
import buyback_event_builder_v5 as builder

# Override universe file
builder.UNIVERSE_FILE = '/home/ubuntu/ares7-ensemble/data/universe/sp100_test.csv'
builder.OUTPUT_FILE = '/home/ubuntu/ares7-ensemble/data/buyback/buyback_events_v5_test.csv'
builder.LOG_FILE = '/home/ubuntu/ares7-ensemble/data/buyback/extraction_log_v5_test.json'

# Run main
if __name__ == "__main__":
    builder.main()
