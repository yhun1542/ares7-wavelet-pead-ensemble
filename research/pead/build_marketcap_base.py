#!/usr/bin/env python3
"""
Build Market-Cap Weighted Base Portfolio
=========================================

Creates date/symbol/weight CSV based on market capitalization.
More realistic than Equal-Weight, simpler than full ARES7 weights.

Usage:
    python build_marketcap_base.py

Output:
    /home/ubuntu/ares7-ensemble/data/ares7_base_weights_marketcap.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path

# Paths
DATA_DIR = Path('/home/ubuntu/ares7-ensemble/data')
FUNDAMENTALS_FILE = DATA_DIR / 'fundamentals_with_sector.csv'
PRICES_FILE = DATA_DIR / 'prices.csv'
OUTPUT_FILE = DATA_DIR / 'ares7_base_weights_marketcap.csv'

# Date range (align with PEAD analysis)
START_DATE = '2018-01-01'
END_DATE = '2025-12-31'


def load_fundamentals():
    """Load fundamentals data with market cap"""
    print("Loading fundamentals...")
    
    if not FUNDAMENTALS_FILE.exists():
        raise FileNotFoundError(f"Fundamentals file not found: {FUNDAMENTALS_FILE}")
    
    df = pd.read_csv(FUNDAMENTALS_FILE)
    
    # Check for marketcap column
    if 'marketcap' not in df.columns:
        # Try alternative column names
        for col in ['market_cap', 'mktcap', 'mcap', 'capitalization']:
            if col in df.columns:
                print(f"Using '{col}' as marketcap")
                df['marketcap'] = df[col]
                break
        else:
            print("⚠️  No market cap column found in fundamentals")
            print("Available columns:", df.columns.tolist())
            raise ValueError("No market cap column found in fundamentals")
    
    # Convert date (handle both 'date' and 'report_date')
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    elif 'report_date' in df.columns:
        df['date'] = pd.to_datetime(df['report_date'])
    else:
        raise ValueError("No date column found in fundamentals")
    
    # Filter date range
    df = df[(df['date'] >= START_DATE) & (df['date'] <= END_DATE)]
    
    # Keep only necessary columns
    df = df[['date', 'symbol', 'marketcap']].copy()
    
    # Remove invalid market caps
    df = df[df['marketcap'] > 0].copy()
    
    print(f"✅ Loaded {len(df)} records")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Unique tickers: {df['symbol'].nunique()}")
    
    return df


def load_prices():
    """Load price data to get trading dates"""
    print("\nLoading prices for trading dates...")
    
    if not PRICES_FILE.exists():
        raise FileNotFoundError(f"Prices file not found: {PRICES_FILE}")
    
    df = pd.read_csv(PRICES_FILE)
    
    # Handle both 'date' and 'timestamp' columns
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
    elif 'timestamp' in df.columns:
        df['date'] = pd.to_datetime(df['timestamp'])
    else:
        raise ValueError("No date/timestamp column found in prices")
    
    # Filter date range
    df = df[(df['date'] >= START_DATE) & (df['date'] <= END_DATE)]
    
    # Get unique trading dates
    trading_dates = sorted(df['date'].unique())
    
    print(f"✅ Found {len(trading_dates)} trading dates")
    
    return trading_dates


def forward_fill_marketcap(fund_df, trading_dates):
    """
    Forward-fill market cap for each ticker on trading dates
    
    Returns:
        DataFrame with columns: date, symbol, marketcap
    """
    print("\nForward-filling market cap...")
    
    # Get all tickers
    tickers = sorted(fund_df['symbol'].unique())
    
    # Create full date × ticker grid
    full_index = pd.MultiIndex.from_product(
        [trading_dates, tickers],
        names=['date', 'symbol']
    )
    
    # Pivot fundamentals to date × ticker
    pivot = fund_df.pivot_table(
        index='date',
        columns='symbol',
        values='marketcap',
        aggfunc='last'  # Take last value if multiple per day
    )
    
    # Reindex to all trading dates
    pivot = pivot.reindex(trading_dates)
    
    # Forward fill (use last known market cap)
    pivot = pivot.fillna(method='ffill')
    
    # Also backward fill for early dates (if needed)
    pivot = pivot.fillna(method='bfill')
    
    # Convert back to long format
    result = pivot.stack().reset_index()
    result.columns = ['date', 'symbol', 'marketcap']
    
    # Remove any remaining NaN
    result = result.dropna()
    
    print(f"✅ Created {len(result)} date-ticker pairs")
    
    return result


def calculate_marketcap_weights(df):
    """
    Calculate market-cap weights for each date
    
    weight[ticker, date] = marketcap[ticker, date] / sum(marketcap[:, date])
    """
    print("\nCalculating market-cap weights...")
    
    # Group by date and normalize
    df['weight'] = df.groupby('date')['marketcap'].transform(
        lambda x: x / x.sum()
    )
    
    # Sanity check: weights should sum to 1 for each date
    weight_sums = df.groupby('date')['weight'].sum()
    assert np.allclose(weight_sums, 1.0), "Weights don't sum to 1!"
    
    print(f"✅ Calculated weights for {df['date'].nunique()} dates")
    
    # Summary statistics
    print("\nWeight Statistics:")
    print(f"  Mean:   {df['weight'].mean():.4f}")
    print(f"  Median: {df['weight'].median():.4f}")
    print(f"  Min:    {df['weight'].min():.6f}")
    print(f"  Max:    {df['weight'].max():.4f}")
    
    # Top 5 average weights
    print("\nTop 5 Average Weights:")
    top_weights = df.groupby('symbol')['weight'].mean().sort_values(ascending=False).head(5)
    for ticker, w in top_weights.items():
        print(f"  {ticker}: {w*100:.2f}%")
    
    return df[['date', 'symbol', 'weight']]


def main():
    """Main execution"""
    print("=" * 80)
    print("Building Market-Cap Weighted Base Portfolio")
    print("=" * 80)
    print()
    
    # Load data
    fund_df = load_fundamentals()
    trading_dates = load_prices()
    
    # Forward-fill market cap
    mc_df = forward_fill_marketcap(fund_df, trading_dates)
    
    # Calculate weights
    weights_df = calculate_marketcap_weights(mc_df)
    
    # Sort by date and symbol
    weights_df = weights_df.sort_values(['date', 'symbol'])
    
    # Save
    print(f"\nSaving to {OUTPUT_FILE}...")
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    weights_df.to_csv(OUTPUT_FILE, index=False)
    
    print()
    print("=" * 80)
    print("✅ Market-Cap Base Weights Created")
    print("=" * 80)
    print(f"Output file: {OUTPUT_FILE}")
    print(f"Total records: {len(weights_df):,}")
    print(f"Date range: {weights_df['date'].min()} to {weights_df['date'].max()}")
    print(f"Unique tickers: {weights_df['symbol'].nunique()}")
    print()
    print("Next step:")
    print("  python -m research.pead.run_ares8_overlay --base_weights marketcap")
    print()


if __name__ == '__main__':
    main()
