#!/usr/bin/env python3
"""
Yahoo Finance Analyst Estimates 테스트
"""

import yfinance as yf
import pandas as pd

# 테스트 티커
test_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META']

print("=== Testing Yahoo Finance Analyst Estimates ===\n")

for ticker in test_tickers:
    print(f"\n{'='*60}")
    print(f"Ticker: {ticker}")
    print('='*60)
    
    try:
        stock = yf.Ticker(ticker)
        
        # Analyst Recommendations
        print("\n1. Analyst Recommendations:")
        if hasattr(stock, 'recommendations') and stock.recommendations is not None:
            print(stock.recommendations.tail())
        else:
            print("  No data available")
        
        # Earnings Estimates
        print("\n2. Earnings Estimates:")
        if hasattr(stock, 'earnings_estimate') and stock.earnings_estimate is not None:
            print(stock.earnings_estimate)
        else:
            print("  No data available")
        
        # Revenue Estimates
        print("\n3. Revenue Estimates:")
        if hasattr(stock, 'revenue_estimate') and stock.revenue_estimate is not None:
            print(stock.revenue_estimate)
        else:
            print("  No data available")
        
        # Earnings History
        print("\n4. Earnings History:")
        if hasattr(stock, 'earnings_history') and stock.earnings_history is not None:
            print(stock.earnings_history)
        else:
            print("  No data available")
        
        # Calendar (upcoming earnings)
        print("\n5. Earnings Calendar:")
        if hasattr(stock, 'calendar') and stock.calendar is not None:
            print(stock.calendar)
        else:
            print("  No data available")
        
    except Exception as e:
        print(f"  Error: {e}")

print("\n" + "="*60)
print("Test Complete")
print("="*60)
