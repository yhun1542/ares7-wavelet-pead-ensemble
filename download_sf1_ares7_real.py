#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download SF1 Fundamentals for ARES7-Best Universe
==================================================
Real 100 tickers from prices.csv
"""

import pandas as pd
import nasdaqdatalink as ndl
import time
from pathlib import Path

# Sharadar API Key
SF1_API_KEY = "H6zH4Q2CDr9uTFk9koqJ"
ndl.ApiConfig.api_key = SF1_API_KEY

BASE_DIR = Path(__file__).parent


def load_ares7_universe():
    """Load ARES7-Best universe from prices.csv"""
    prices_file = BASE_DIR / 'data' / 'prices.csv'
    df = pd.read_csv(prices_file)
    tickers = sorted(df['symbol'].unique())
    print(f"✅ ARES7-Best Universe: {len(tickers)} tickers")
    return tickers


def download_sf1_for_ticker(ticker, start_date="2015-01-01", end_date="2025-12-31"):
    """Download SF1 fundamentals for a single ticker"""
    try:
        df = ndl.get_table(
            'SHARADAR/SF1',
            ticker=ticker,
            dimension='MRQ',  # Most Recent Quarter
            calendardate={'gte': start_date, 'lte': end_date},
            qopts={'columns': ['ticker', 'dimension', 'calendardate', 'datekey', 
                              'roe', 'ebitda', 'revenue', 'debt', 'equity']},
            paginate=True
        )
        
        if not df.empty:
            # Calculate derived metrics
            df['ebitdamargin'] = df['ebitda'] / df['revenue']
            df['de'] = df['debt'] / df['equity']
            
            # Clean up
            df = df.replace([float('inf'), float('-inf')], None)
            
            return df
        else:
            return pd.DataFrame()
    
    except Exception as e:
        print(f"  ❌ Error for {ticker}: {e}")
        return pd.DataFrame()


def download_sf1_all(tickers, start_date="2015-01-01", end_date="2025-12-31"):
    """Download SF1 for all tickers"""
    print("="*80)
    print("Downloading SF1 Fundamentals from Sharadar")
    print("="*80)
    
    all_data = []
    
    for i, ticker in enumerate(tickers):
        print(f"[{i+1}/{len(tickers)}] {ticker}...", end=" ")
        
        df = download_sf1_for_ticker(ticker, start_date, end_date)
        
        if not df.empty:
            all_data.append(df)
            print(f"✅ {len(df)} records")
        else:
            print("⚠️  No data")
        
        # Rate limit
        time.sleep(0.3)
    
    if not all_data:
        print("\n❌ No data downloaded")
        return None
    
    # Combine
    combined = pd.concat(all_data, ignore_index=True)
    combined['calendardate'] = pd.to_datetime(combined['calendardate'])
    combined['datekey'] = pd.to_datetime(combined['datekey'])
    
    # Clean
    combined = combined.dropna(subset=['roe', 'ebitdamargin', 'de'])
    
    print(f"\n✅ Total: {len(combined)} records")
    print(f"   Tickers: {combined['ticker'].nunique()}")
    print(f"   Date range: {combined['datekey'].min().date()} ~ {combined['datekey'].max().date()}")
    
    return combined


def main():
    print("Starting SF1 Download for ARES7-Best Universe...")
    
    # Load universe
    tickers = load_ares7_universe()
    
    # Download SF1
    fundamentals = download_sf1_all(tickers, start_date='2015-01-01', end_date='2025-12-31')
    
    if fundamentals is None or len(fundamentals) == 0:
        print("\n❌ Download failed")
        return
    
    # Save
    output_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals.csv'
    fundamentals.to_csv(output_file, index=False)
    
    print(f"\n✅ Saved to: {output_file}")
    
    # Sample
    print(f"\n📋 Sample Data:")
    print(fundamentals.head(10))
    
    # Statistics
    print(f"\n📊 Statistics:")
    print(fundamentals[['roe', 'ebitdamargin', 'de']].describe())


if __name__ == "__main__":
    main()
