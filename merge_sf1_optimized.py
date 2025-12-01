#!/usr/bin/env python3
"""
Optimized SF1 Fundamentals Merge
=================================
Fast point-in-time merge using NumPy + binary search
"""

import pandas as pd
import numpy as np
from numba import njit
import time


@njit(cache=True)
def find_latest_before_numba(sf1_dates, target_date):
    """Binary search to find latest SF1 date before target_date"""
    
    # Binary search
    left = 0
    right = len(sf1_dates) - 1
    result = -1
    
    while left <= right:
        mid = (left + right) // 2
        
        if sf1_dates[mid] <= target_date:
            result = mid
            left = mid + 1
        else:
            right = mid - 1
    
    return result


def merge_sf1_optimized(returns_df, sf1_df):
    """
    Optimized SF1 merge using binary search
    
    Args:
        returns_df: DataFrame with returns (dates × symbols)
        sf1_df: SF1 fundamentals DataFrame
    
    Returns:
        quality_df: Quality scores aligned with returns
    """
    
    print("\n🔗 Merging SF1 data (OPTIMIZED)...")
    start_time = time.time()
    
    dates = returns_df.index.values
    symbols = returns_df.columns.values
    n_dates = len(dates)
    n_symbols = len(symbols)
    
    # Convert dates to int64 for faster comparison
    dates_int = dates.astype('datetime64[D]').astype(np.int64)
    
    # Pre-allocate quality matrix
    quality_matrix = np.full((n_dates, n_symbols), np.nan, dtype=np.float32)
    
    # Process each symbol
    for j, ticker in enumerate(symbols):
        if j % 10 == 0:
            print(f"   Processing {j}/{n_symbols}...")
        
        # Get SF1 data for this ticker
        ticker_sf1 = sf1_df[sf1_df['ticker'] == ticker].copy()
        
        if len(ticker_sf1) == 0:
            continue
        
        # Sort by date
        ticker_sf1 = ticker_sf1.sort_values('datekey')
        
        # Convert to int64
        sf1_dates = ticker_sf1['datekey'].values.astype('datetime64[D]').astype(np.int64)
        
        # Extract quality metrics
        roe = ticker_sf1['roe'].fillna(0.0).values
        ebitda_margin = ticker_sf1['ebitdamargin'].fillna(0.0).values
        de = ticker_sf1['de'].fillna(1.0).values
        
        # Compute quality scores
        quality_scores = 0.5 * roe + 0.3 * ebitda_margin - 0.2 * de
        
        # For each date, find latest SF1 data
        for i in range(n_dates):
            target_date = dates_int[i]
            
            # Binary search
            idx = find_latest_before_numba(sf1_dates, target_date)
            
            if idx >= 0:
                quality_matrix[i, j] = quality_scores[idx]
    
    # Convert to DataFrame
    quality_df = pd.DataFrame(
        quality_matrix,
        index=returns_df.index,
        columns=returns_df.columns
    )
    
    # Fill missing with median
    quality_df = quality_df.fillna(quality_df.median())
    
    elapsed = time.time() - start_time
    
    print(f"\n✅ SF1 Merge Complete!")
    print(f"   Time: {elapsed:.2f} seconds")
    print(f"   Speed: {n_dates * n_symbols / elapsed:.0f} cells/second")
    print(f"   Coverage: {quality_df.notna().sum().sum() / quality_df.size * 100:.1f}%")
    
    return quality_df


if __name__ == "__main__":
    print("Optimized SF1 Merge Module Ready!")
