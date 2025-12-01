#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download VIX from FRED API
===========================
"""

import pandas as pd
import requests
from datetime import datetime

FRED_API_KEY = "b4a5371d46459ba15138393980de28d5"
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

def download_vix_from_fred(start_date='2015-01-01', end_date='2025-12-31'):
    """
    Download VIX from FRED
    Series: VIXCLS (CBOE Volatility Index: VIX)
    """
    print("="*80)
    print("Downloading VIX from FRED API")
    print("="*80)
    
    params = {
        'series_id': 'VIXCLS',
        'api_key': FRED_API_KEY,
        'file_type': 'json',
        'observation_start': start_date,
        'observation_end': end_date,
    }
    
    try:
        response = requests.get(FRED_BASE_URL, params=params)
        response.raise_for_status()
        
        data = response.json()
        
        if 'observations' not in data:
            print(f"❌ No data returned from FRED")
            return None
        
        observations = data['observations']
        
        # Convert to DataFrame
        df = pd.DataFrame(observations)
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        df = df.dropna(subset=['value'])
        df = df.set_index('date')
        
        vix_series = df['value'].rename('vix_close')
        
        print(f"✅ VIX data downloaded from FRED")
        print(f"   Series: VIXCLS (CBOE Volatility Index)")
        print(f"   Period: {vix_series.index[0].date()} ~ {vix_series.index[-1].date()}")
        print(f"   Days: {len(vix_series)}")
        print(f"   Mean: {vix_series.mean():.2f}")
        print(f"   Std: {vix_series.std():.2f}")
        print(f"   Range: [{vix_series.min():.2f}, {vix_series.max():.2f}]")
        
        # Show crisis periods
        print(f"\n📊 Crisis Period VIX Levels:")
        
        # 2018 Q4
        mask_2018 = (vix_series.index >= '2018-12-01') & (vix_series.index <= '2018-12-31')
        if mask_2018.any():
            print(f"   2018 Q4: Mean={vix_series[mask_2018].mean():.2f}, Max={vix_series[mask_2018].max():.2f}")
        
        # 2020 COVID
        mask_2020 = (vix_series.index >= '2020-02-15') & (vix_series.index <= '2020-04-30')
        if mask_2020.any():
            print(f"   2020 COVID: Mean={vix_series[mask_2020].mean():.2f}, Max={vix_series[mask_2020].max():.2f}")
        
        # 2022 Ukraine
        mask_2022 = (vix_series.index >= '2022-02-20') & (vix_series.index <= '2022-03-31')
        if mask_2022.any():
            print(f"   2022 Ukraine: Mean={vix_series[mask_2022].mean():.2f}, Max={vix_series[mask_2022].max():.2f}")
        
        return vix_series
    
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to download from FRED: {e}")
        return None
    except Exception as e:
        print(f"❌ Error processing FRED data: {e}")
        return None


def main():
    # Download VIX
    vix = download_vix_from_fred(start_date='2015-01-01', end_date='2025-12-31')
    
    if vix is None:
        print("\n❌ Failed to download VIX data")
        return
    
    # Save to CSV
    output_file = '/home/ubuntu/ares7-ensemble/data/vix_data.csv'
    vix.to_csv(output_file)
    print(f"\n✅ VIX data saved to: {output_file}")
    
    # Show sample
    print(f"\n📋 Sample Data:")
    print(vix.head(10))
    print("...")
    print(vix.tail(10))


if __name__ == "__main__":
    main()
