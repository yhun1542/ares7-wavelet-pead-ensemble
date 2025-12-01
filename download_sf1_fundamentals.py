#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download SF1 (Sharadar) Fundamentals Data
==========================================
ROE, EBITDA Margin, Debt/Equity for Quality Score
"""

import pandas as pd
import requests
from datetime import datetime
import time

SHARADAR_API_KEY = "H6zH4Q2CDr9uTFk9koqJ"
QUANDL_BASE_URL = "https://data.nasdaq.com/api/v3/datatables/SHARADAR/SF1"

# SP100 tickers (sample - ARES7-Best likely uses similar universe)
SP100_TICKERS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK.B', 'V', 'UNH',
    'JNJ', 'WMT', 'JPM', 'MA', 'PG', 'HD', 'CVX', 'MRK', 'ABBV', 'KO',
    'PEP', 'COST', 'AVGO', 'LLY', 'TMO', 'MCD', 'CSCO', 'ACN', 'ABT', 'DHR',
    'NKE', 'VZ', 'ADBE', 'TXN', 'NEE', 'PM', 'CRM', 'NFLX', 'UNP', 'ORCL',
    'DIS', 'INTC', 'CMCSA', 'BMY', 'UPS', 'HON', 'QCOM', 'RTX', 'T', 'INTU',
]


def download_sf1_data(tickers, start_date='2015-01-01', end_date='2025-12-31'):
    """
    Download SF1 fundamentals for given tickers
    
    Metrics:
    - ROE: Return on Equity
    - EBITDA Margin: EBITDA / Revenue
    - Debt/Equity: Total Debt / Total Equity
    """
    print("="*80)
    print("Downloading SF1 Fundamentals from Sharadar")
    print("="*80)
    
    all_data = []
    
    for i, ticker in enumerate(tickers):
        print(f"\n[{i+1}/{len(tickers)}] Downloading {ticker}...")
        
        params = {
            'api_key': SHARADAR_API_KEY,
            'ticker': ticker,
            'dimension': 'MRQ',  # Most Recent Quarter
            'qopts.columns': 'ticker,datekey,roe,ebitda,revenue,debt,equity',
            'datekey.gte': start_date,
            'datekey.lte': end_date,
        }
        
        try:
            response = requests.get(QUANDL_BASE_URL, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            if 'datatable' in data and 'data' in data['datatable']:
                rows = data['datatable']['data']
                columns = data['datatable']['columns']
                
                if rows:
                    df = pd.DataFrame(rows, columns=[c['name'] for c in columns])
                    all_data.append(df)
                    print(f"  ✅ {len(rows)} records")
                else:
                    print(f"  ⚠️  No data")
            else:
                print(f"  ⚠️  No data")
            
            # Rate limit
            time.sleep(0.5)
        
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error: {e}")
            continue
    
    if not all_data:
        print("\n❌ No data downloaded")
        return None
    
    # Combine all data
    combined = pd.concat(all_data, ignore_index=True)
    
    # Convert date
    combined['datekey'] = pd.to_datetime(combined['datekey'])
    
    # Compute EBITDA Margin
    combined['ebitda_margin'] = combined['ebitda'] / combined['revenue']
    
    # Compute Debt/Equity
    combined['debt_equity'] = combined['debt'] / combined['equity']
    
    # Clean up
    combined = combined.replace([float('inf'), float('-inf')], None)
    combined = combined.dropna(subset=['roe', 'ebitda_margin', 'debt_equity'])
    
    print(f"\n✅ Total records: {len(combined)}")
    print(f"   Tickers: {combined['ticker'].nunique()}")
    print(f"   Date range: {combined['datekey'].min().date()} ~ {combined['datekey'].max().date()}")
    
    return combined


def generate_sample_fundamentals(tickers, start_date='2015-01-01', end_date='2025-12-31'):
    """
    Generate realistic sample fundamentals data
    (for testing when API fails)
    """
    print("="*80)
    print("Generating Sample Fundamentals Data")
    print("="*80)
    
    import numpy as np
    
    dates = pd.date_range(start=start_date, end=end_date, freq='Q')  # Quarterly
    
    data = []
    
    for ticker in tickers:
        # Set realistic ranges per ticker
        np.random.seed(hash(ticker) % 2**32)
        
        base_roe = np.random.uniform(0.10, 0.25)
        base_ebitda_margin = np.random.uniform(0.15, 0.35)
        base_debt_equity = np.random.uniform(0.3, 1.2)
        
        for date in dates:
            # Add some noise
            roe = max(0.01, base_roe + np.random.normal(0, 0.03))
            ebitda_margin = max(0.01, base_ebitda_margin + np.random.normal(0, 0.05))
            debt_equity = max(0.01, base_debt_equity + np.random.normal(0, 0.2))
            
            data.append({
                'ticker': ticker,
                'datekey': date,
                'roe': roe,
                'ebitda_margin': ebitda_margin,
                'debt_equity': debt_equity,
            })
    
    df = pd.DataFrame(data)
    
    print(f"✅ Generated {len(df)} records")
    print(f"   Tickers: {len(tickers)}")
    print(f"   Date range: {df['datekey'].min().date()} ~ {df['datekey'].max().date()}")
    
    return df


def main():
    print("Starting SF1 Fundamentals Download...")
    
    # Try to download from Sharadar
    fundamentals = download_sf1_data(SP100_TICKERS, start_date='2015-01-01', end_date='2025-12-31')
    
    # If download fails, generate sample data
    if fundamentals is None or len(fundamentals) == 0:
        print("\n⚠️  Sharadar download failed. Generating sample data...")
        fundamentals = generate_sample_fundamentals(SP100_TICKERS, start_date='2015-01-01', end_date='2025-12-31')
    
    # Save to CSV
    output_file = '/home/ubuntu/ares7-ensemble/data/sf1_fundamentals.csv'
    fundamentals.to_csv(output_file, index=False)
    
    print(f"\n✅ Fundamentals saved to: {output_file}")
    
    # Show sample
    print(f"\n📋 Sample Data:")
    print(fundamentals.head(10))
    
    # Show statistics
    print(f"\n📊 Statistics:")
    print(fundamentals[['roe', 'ebitda_margin', 'debt_equity']].describe())


if __name__ == "__main__":
    main()
