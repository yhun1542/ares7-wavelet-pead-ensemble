#!/usr/bin/env python3
"""Download SF1 Fundamentals for ARES7-Best (FINAL)"""

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
    print(f"✅ ARES7-Best Universe: {len(tickers)} tickers\n")
    return tickers


def download_sf1_all(tickers):
    print("="*80)
    print("Downloading SF1 Fundamentals (MRT - Most Recent TTM)")
    print("="*80)
    
    all_data = []
    
    for i, ticker in enumerate(tickers):
        print(f"[{i+1:3d}/100] {ticker:6s}...", end=" ", flush=True)
        
        try:
            df = ndl.get_table(
                'SHARADAR/SF1',
                ticker=ticker,
                dimension='MRT',  # Most Recent TTM
                paginate=True
            )
            
            if not df.empty:
                # Select needed columns
                cols = ['ticker', 'datekey', 'calendardate', 'roe', 'ebitda', 'revenue', 'debt', 'equity']
                df = df[cols].copy()
                
                # Calculate metrics
                df['ebitdamargin'] = df['ebitda'] / df['revenue']
                df['de'] = df['debt'] / df['equity']
                
                all_data.append(df)
                print(f"✅ {len(df):3d} records")
            else:
                print("⚠️  No data")
        
        except Exception as e:
            print(f"❌ {str(e)[:50]}")
        
        time.sleep(0.2)  # Rate limit
    
    if not all_data:
        print("\n❌ No data downloaded")
        return None
    
    # Combine
    combined = pd.concat(all_data, ignore_index=True)
    combined['datekey'] = pd.to_datetime(combined['datekey'])
    combined['calendardate'] = pd.to_datetime(combined['calendardate'])
    
    print(f"\n{'='*80}")
    print(f"✅ Total: {len(combined):,} records")
    print(f"   Tickers: {combined['ticker'].nunique()}")
    print(f"   Date range: {combined['datekey'].min().date()} ~ {combined['datekey'].max().date()}")
    print(f"{'='*80}")
    
    return combined


def main():
    print("\n🚀 Starting SF1 Download for ARES7-Best Universe...\n")
    
    tickers = load_ares7_universe()
    fundamentals = download_sf1_all(tickers)
    
    if fundamentals is None or len(fundamentals) == 0:
        print("\n❌ Download failed")
        return
    
    output_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals.csv'
    fundamentals.to_csv(output_file, index=False)
    
    print(f"\n✅ Saved to: {output_file}")
    print(f"   File size: {output_file.stat().st_size / 1024 / 1024:.2f} MB")
    
    print(f"\n📋 Sample Data:")
    print(fundamentals.head(10))
    
    print(f"\n📊 Statistics:")
    print(fundamentals[['roe', 'ebitdamargin', 'de']].describe())
    
    print(f"\n✅ SF1 Download Complete!")


if __name__ == "__main__":
    main()
