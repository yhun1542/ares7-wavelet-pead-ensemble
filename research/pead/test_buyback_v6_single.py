#!/usr/bin/env python3
"""
Test script for Buyback Event Builder v6 - Single Ticker (AAPL)
"""

import os
import sys

# Import the main script
sys.path.insert(0, '/home/ubuntu/ares7-ensemble/research/pead')

# Modify constants
import buyback_event_builder_v6 as builder

# Override universe file
builder.UNIVERSE_FILE = '/home/ubuntu/ares7-ensemble/data/universe/sp100_single.csv'
builder.OUTPUT_FILE = '/home/ubuntu/ares7-ensemble/data/buyback/buyback_events_v6_single.csv'
builder.LOG_FILE = '/home/ubuntu/ares7-ensemble/data/buyback/extraction_log_v6_single.json'

# Run main
if __name__ == "__main__":
    builder.main()
