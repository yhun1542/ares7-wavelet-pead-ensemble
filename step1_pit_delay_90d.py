#!/usr/bin/env python3
"""
Step 1: PIT Delay 90일 적용
===========================
Look-ahead bias 완전 제거 (negative lag 0건 달성)
"""

import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent


def fix_pit_delay_90d():
    """Fix PIT delay to 90 days and verify no look-ahead bias"""
    
    print("="*80)
    print("Step 1: PIT Delay 90일 적용")
    print("="*80)
    
    # Load SF1 data
    print(f"\n📂 Loading SF1 data...")
    sf1_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals.csv'
    sf1_df = pd.read_csv(sf1_file, parse_dates=['datekey', 'calendardate'])
    
    print(f"   Original records: {len(sf1_df)}")
    
    # Method: effective_date = max(calendardate, datekey) + delay
    delay_days = 90
    
    print(f"\n🔧 Applying PIT delay...")
    print(f"   Method: effective_date = max(calendardate, datekey) + {delay_days} days")
    
    # Calculate effective_date
    sf1_df['effective_date'] = sf1_df[['calendardate', 'datekey']].max(axis=1) + pd.Timedelta(days=delay_days)
    
    # Safety check: effective_date >= calendardate
    sf1_df = sf1_df[sf1_df['effective_date'] >= sf1_df['calendardate']].copy()
    
    print(f"   Records after filter: {len(sf1_df)}")
    
    # Check lag
    sf1_df['lag_days'] = (sf1_df['effective_date'] - sf1_df['calendardate']).dt.days
    
    print(f"\n📊 Lag Statistics (days):")
    print(f"   Mean: {sf1_df['lag_days'].mean():.1f}")
    print(f"   Median: {sf1_df['lag_days'].median():.1f}")
    print(f"   Min: {sf1_df['lag_days'].min():.1f}")
    print(f"   Max: {sf1_df['lag_days'].max():.1f}")
    
    # Check negative lag
    negative_lag = sf1_df[sf1_df['lag_days'] < 0]
    
    if len(negative_lag) > 0:
        print(f"\n❌ STILL {len(negative_lag)} records with negative lag!")
        print(f"   Increasing delay...")
        
        # Try 120 days
        delay_days = 120
        sf1_df['effective_date'] = sf1_df[['calendardate', 'datekey']].max(axis=1) + pd.Timedelta(days=delay_days)
        sf1_df = sf1_df[sf1_df['effective_date'] >= sf1_df['calendardate']].copy()
        sf1_df['lag_days'] = (sf1_df['effective_date'] - sf1_df['calendardate']).dt.days
        
        negative_lag = sf1_df[sf1_df['lag_days'] < 0]
        
        if len(negative_lag) > 0:
            print(f"   ❌ STILL {len(negative_lag)} records with {delay_days} days delay!")
        else:
            print(f"   ✅ NO negative lag with {delay_days} days delay!")
    else:
        print(f"\n✅ NO LOOK-AHEAD BIAS!")
        print(f"   All records have lag >= 0 days")
    
    # Replace datekey with effective_date
    sf1_df['datekey'] = sf1_df['effective_date']
    sf1_df = sf1_df.drop(columns=['effective_date', 'lag_days'])
    
    # Save fixed SF1 data
    output_file = BASE_DIR / 'data' / f'ares7_sf1_fundamentals_pit{delay_days}d.csv'
    sf1_df.to_csv(output_file, index=False)
    
    print(f"\n✅ Fixed SF1 data saved: {output_file}")
    print(f"   Delay: {delay_days} days")
    print(f"   Records: {len(sf1_df)}")
    
    # Sample check
    print(f"\n📋 Sample: AAPL (first 10 records)")
    ticker_sf1 = sf1_df[sf1_df['ticker'] == 'AAPL'].sort_values('datekey').head(10)
    
    print(f"\n{'datekey':<12} {'calendardate':<15} {'ROE':<8} {'EBITDA Margin':<15}")
    print("-" * 80)
    
    for idx, row in ticker_sf1.iterrows():
        datekey = row['datekey'].strftime('%Y-%m-%d')
        calendardate = row['calendardate'].strftime('%Y-%m-%d')
        roe = f"{row['roe']:.4f}" if pd.notna(row['roe']) else 'NaN'
        ebitda = f"{row['ebitdamargin']:.4f}" if pd.notna(row['ebitdamargin']) else 'NaN'
        
        print(f"{datekey:<12} {calendardate:<15} {roe:<8} {ebitda:<15}")
    
    print(f"\n" + "="*80)
    print(f"✅ Step 1 Complete: PIT Delay {delay_days}일 적용")
    print("="*80)
    
    return delay_days, output_file


if __name__ == "__main__":
    delay_days, output_file = fix_pit_delay_90d()
    print(f"\n📌 Next: Use {output_file} for OOS-based Grid Search")
