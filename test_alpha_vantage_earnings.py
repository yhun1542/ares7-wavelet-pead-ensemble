#!/usr/bin/env python3
"""
Alpha Vantage Earnings 데이터 테스트
"""

import requests
import json
import time

API_KEY = "WA6OEWIF23A4LVGN"
BASE_URL = "https://www.alphavantage.co/query"

# 테스트 티커
test_tickers = ['AAPL', 'MSFT', 'GOOGL']

print("=== Testing Alpha Vantage Earnings Data ===\n")

for ticker in test_tickers:
    print(f"\n{'='*60}")
    print(f"Ticker: {ticker}")
    print('='*60)
    
    # 1. Earnings (Quarterly & Annual)
    print("\n1. EARNINGS (Quarterly & Annual):")
    try:
        params = {
            'function': 'EARNINGS',
            'symbol': ticker,
            'apikey': API_KEY
        }
        response = requests.get(BASE_URL, params=params)
        data = response.json()
        
        if 'quarterlyEarnings' in data:
            print(f"  Quarterly Earnings: {len(data['quarterlyEarnings'])} records")
            print("  Sample (latest 3):")
            for item in data['quarterlyEarnings'][:3]:
                print(f"    {item}")
        
        if 'annualEarnings' in data:
            print(f"\n  Annual Earnings: {len(data['annualEarnings'])} records")
            print("  Sample (latest 3):")
            for item in data['annualEarnings'][:3]:
                print(f"    {item}")
        
        if 'Note' in data or 'Error Message' in data:
            print(f"  API Response: {data}")
        
    except Exception as e:
        print(f"  Error: {e}")
    
    time.sleep(12)  # API rate limit (5 calls/min for free tier)
    
    # 2. Earnings Calendar (upcoming)
    print("\n2. EARNINGS CALENDAR:")
    try:
        params = {
            'function': 'EARNINGS_CALENDAR',
            'symbol': ticker,
            'apikey': API_KEY
        }
        response = requests.get(BASE_URL, params=params)
        
        # CSV format response
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            print(f"  Records: {len(lines)-1}")
            print("  Sample (first 5 lines):")
            for line in lines[:5]:
                print(f"    {line}")
        else:
            print(f"  Error: {response.status_code}")
    
    except Exception as e:
        print(f"  Error: {e}")
    
    time.sleep(12)

print("\n" + "="*60)
print("Test Complete")
print("="*60)
