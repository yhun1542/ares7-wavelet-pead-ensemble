#!/usr/bin/env python3
"""
Download ETF price data from Polygon API for ARES-7 ETF Momentum Engine

ETF Universe:
- Broad Market: SPY, QQQ, IWM
- Sectors: XLF, XLE, XLV, XLK, XLI, XLY, XLP, XLU, XLB
- International: EFA, EEM
- Bonds: TLT, IEF
- Commodities: GLD, USO
"""

import os
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# Polygon API Key
API_KEY = os.environ.get('POLYGON_API_KEY', 'w7KprL4_lK7uutSH0dYGARkucXHOFXCN')

# ETF Universe
ETF_UNIVERSE = [
    # Broad Market
    'SPY',   # S&P 500
    'QQQ',   # Nasdaq 100
    'IWM',   # Russell 2000
    
    # Sectors
    'XLF',   # Financials
    'XLE',   # Energy
    'XLV',   # Healthcare
    'XLK',   # Technology
    'XLI',   # Industrials
    'XLY',   # Consumer Discretionary
    'XLP',   # Consumer Staples
    'XLU',   # Utilities
    'XLB',   # Materials
    
    # International
    'EFA',   # EAFE (Developed Markets)
    'EEM',   # Emerging Markets
    
    # Bonds
    'TLT',   # 20+ Year Treasury
    'IEF',   # 7-10 Year Treasury
    
    # Commodities
    'GLD',   # Gold
    'USO',   # Oil
]

# Date range (same as stock data: 2015-11-23 to 2025-11-22)
START_DATE = '2015-11-23'
END_DATE = '2025-11-22'

def download_etf_bars(symbol, start_date, end_date, api_key):
    """Download daily bars for a single ETF from Polygon"""
    
    url = f'https://api.polygon.io/v2/aggs/ticker/{symbol}/range/1/day/{start_date}/{end_date}'
    params = {
        'adjusted': 'true',
        'sort': 'asc',
        'limit': 50000,
        'apiKey': api_key
    }
    
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get('status') != 'OK' or 'results' not in data:
            print(f"  ⚠️  {symbol}: No data (status={data.get('status')})")
            return None
        
        results = data['results']
        df = pd.DataFrame(results)
        
        # Convert timestamp (ms) to datetime
        df['timestamp'] = pd.to_datetime(df['t'], unit='ms', utc=True)
        df['timestamp'] = df['timestamp'].dt.tz_localize(None)
        
        # Rename columns to match stock data format
        df = df.rename(columns={
            'o': 'open',
            'h': 'high',
            'l': 'low',
            'c': 'close',
            'v': 'volume',
            'vw': 'vwap'
        })
        
        # Add symbol
        df['symbol'] = symbol
        
        # Select columns
        df = df[['symbol', 'timestamp', 'open', 'high', 'low', 'close', 'volume', 'vwap']]
        
        print(f"  ✅ {symbol}: {len(df)} bars downloaded")
        return df
        
    except Exception as e:
        print(f"  ❌ {symbol}: Error - {str(e)}")
        return None

def main():
    if not API_KEY:
        print("❌ Error: POLYGON_API_KEY environment variable not set")
        return
    
    print("=" * 60)
    print("ETF Data Download from Polygon API")
    print("=" * 60)
    print(f"Universe: {len(ETF_UNIVERSE)} ETFs")
    print(f"Period: {START_DATE} to {END_DATE}")
    print("=" * 60)
    
    all_data = []
    
    for i, symbol in enumerate(ETF_UNIVERSE, 1):
        print(f"[{i}/{len(ETF_UNIVERSE)}] Downloading {symbol}...")
        
        df = download_etf_bars(symbol, START_DATE, END_DATE, API_KEY)
        
        if df is not None:
            all_data.append(df)
        
        # Rate limiting: 5 requests per minute for free tier
        if i < len(ETF_UNIVERSE):
            time.sleep(12)  # 12 seconds between requests = 5 per minute
    
    print("=" * 60)
    
    if not all_data:
        print("❌ No data downloaded. Exiting.")
        return
    
    # Combine all ETF data
    combined = pd.concat(all_data, ignore_index=True)
    combined = combined.sort_values(['symbol', 'timestamp']).reset_index(drop=True)
    
    # Save to CSV
    output_path = './data/etf_price.csv'
    combined.to_csv(output_path, index=False)
    
    print(f"✅ Data saved to {output_path}")
    print(f"   Total records: {len(combined):,}")
    print(f"   Symbols: {combined['symbol'].nunique()}")
    print(f"   Date range: {combined['timestamp'].min()} to {combined['timestamp'].max()}")
    
    # Summary by symbol
    print("\n" + "=" * 60)
    print("Summary by Symbol:")
    print("=" * 60)
    summary = combined.groupby('symbol').agg({
        'timestamp': ['min', 'max', 'count']
    }).round(0)
    summary.columns = ['Start Date', 'End Date', 'Bars']
    print(summary)

if __name__ == '__main__':
    main()
