#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download SF1 Fundamentals for ARES7-Best Universe (FIXED)
==========================================================
"""

import pandas as pd
import nasdaqdatalink as ndl
import time
from pathlib import Path

SF1_API_KEY = "H6zH4Q2CDr9uTFk9koqJ"
ndl.ApiConfig.api_key = SF1_API_KEY

BASE_DIR = Path(__file__).parent


def load_ares7_universe():
    prices_file = BASE_DIR / 'data' / 'prices.csv'
    df = pd.read_csv(prices_file)
    tickers = sorted(df['symbol'].unique())
    print(f"✅ ARES7-Best Universe: {len(tickers)} tickers")
    return tickers


def download_sf1_all(tickers, start_date="2015-01-01", end_date="2025-12-31"):
    print("="*80)
    print("Downloading SF1 Fundamentals")
    print("="*80)
    
    all_data = []
    
    for i, ticker in enumerate(tickers):
        print(f"[{i+1}/{len(tickers)}] {ticker}...", end=" ", flush=True)
        
        try:
            df = ndl.get_table(
                'SHARADAR/SF1',
                ticker=ticker,
                dimension='MRQ',
                calendardate={'gte': start_date, 'lte': end_date},
                qopts={'columns': ['ticker', 'dimension', 'calendardate', 'datekey', 
                                  'roe', 'ebitda', 'revenue', 'debt', 'equity']},
                paginate=True
            )
            
            if not df.empty:
                # Calculate metrics
                df['ebitdamargin'] = df['ebitda'] / df['revenue'].replace(0, 1e-10)
                df['de'] = df['debt'] / df['equity'].replace(0, 1e-10)
                
                # Clean inf
                df['ebitdamargin'] = df['ebitdamargin'].replace([float('inf'), float('-inf')], None)
                df['de'] = df['de'].replace([float('inf'), float('-inf')], None)
                
                all_data.append(df)
                print(f"✅ {len(df)}")
            else:
                print("⚠️  No data")
        
        except Exception as e:
            print(f"❌ {e}")
        
        time.sleep(0.3)
    
    if not all_data:
        print("\n❌ No data downloaded")
        return None
    
    # Combine
    combined = pd.concat(all_data, ignore_index=True)
    combined['calendardate'] = pd.to_datetime(combined['calendardate'])
    combined['datekey'] = pd.to_datetime(combined['datekey'])
    
    # Drop rows with missing critical data
    before = len(combined)
    combined = combined.dropna(subset=['roe', 'ebitdamargin', 'de'])
    after = len(combined)
    
    print(f"\n✅ Total: {after} records (dropped {before-after} with missing data)")
    print(f"   Tickers: {combined['ticker'].nunique()}")
    print(f"   Date range: {combined['datekey'].min().date()} ~ {combined['datekey'].max().date()}")
    
    return combined


def main():
    print("Starting SF1 Download...")
    
    tickers = load_ares7_universe()
    fundamentals = download_sf1_all(tickers)
    
    if fundamentals is None or len(fundamentals) == 0:
        print("\n❌ Download failed")
        return
    
    output_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals.csv'
    fundamentals.to_csv(output_file, index=False)
    
    print(f"\n✅ Saved to: {output_file}")
    print(f"\n📋 Sample:")
    print(fundamentals.head(10))
    print(f"\n📊 Statistics:")
    print(fundamentals[['roe', 'ebitdamargin', 'de']].describe())


if __name__ == "__main__":
    main()
