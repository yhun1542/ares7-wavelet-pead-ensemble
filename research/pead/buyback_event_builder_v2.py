#!/usr/bin/env python3
"""
Buyback Event Builder (v2 - 가이드 구조)
raw buyback CSV → buyback event table (bucket, signal_rank, split)
"""

import pandas as pd
import numpy as np


def build_buyback_events(
    raw_bb_df: pd.DataFrame,
    price_index: pd.DatetimeIndex,
    split_cfg: dict,
    use_mc_ratio: bool = False,
):
    """
    Buyback raw data → event table
    
    Parameters:
    -----------
    raw_bb_df : pd.DataFrame
        Required columns: ticker, filing_date, amount_usd
        Optional: marketcap_usd
    price_index : pd.DatetimeIndex
        Price data index (for date alignment)
    split_cfg : dict
        {"train": ("2016-01-01", "2019-12-31"), ...}
    use_mc_ratio : bool
        If True and marketcap_usd exists, use amount/marketcap ratio for ranking
    
    Returns:
    --------
    pd.DataFrame with columns:
        event_date, ticker, amount_usd, signal_rank, bucket, split
    """
    
    df = raw_bb_df.copy()
    
    # 1. Date conversion and normalization
    df['event_date'] = pd.to_datetime(df['filing_date']).dt.normalize()
    
    # 2. Filter: event_date in price_index
    df = df[df['event_date'].isin(price_index)]
    
    if len(df) == 0:
        print("Warning: No buyback events found in price_index range")
        return pd.DataFrame()
    
    # 3. Signal strength
    if use_mc_ratio and 'marketcap_usd' in df.columns:
        # Use amount/marketcap ratio
        df['signal_strength'] = df['amount_usd'] / (df['marketcap_usd'] + 1e-9)
    else:
        # Use absolute amount
        df['signal_strength'] = df['amount_usd']
    
    # 4. Cross-sectional rank (within each event_date)
    def rank_within_date(group):
        group['signal_rank'] = group['signal_strength'].rank(pct=True)
        return group
    
    df = df.groupby('event_date', group_keys=False).apply(rank_within_date)
    
    # 5. Bucket assignment (top 10% = bb_top)
    def bucketize(rank):
        if pd.isna(rank):
            return 'neutral'
        return 'bb_top' if rank >= 0.9 else 'neutral'
    
    df['bucket'] = df['signal_rank'].apply(bucketize)
    
    # 6. Split assignment
    def assign_split(date):
        for split_name, (start, end) in split_cfg.items():
            if pd.to_datetime(start) <= date <= pd.to_datetime(end):
                return split_name
        return 'unknown'
    
    df['split'] = df['event_date'].apply(assign_split)
    
    # 7. Select columns
    result = df[[
        'event_date',
        'ticker',
        'amount_usd',
        'signal_rank',
        'bucket',
        'split'
    ]].copy()
    
    # 8. Sort
    result = result.sort_values(['event_date', 'ticker']).reset_index(drop=True)
    
    print(f"Built {len(result)} buyback events")
    print(f"  bb_top: {(result['bucket'] == 'bb_top').sum()}")
    print(f"  Splits: {result['split'].value_counts().to_dict()}")
    
    return result


def convert_v6_to_standard(v6_df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert v6 buyback format to standard format
    
    v6 format: date, ticker, buyback_amount, ...
    standard format: filing_date, ticker, amount_usd, ...
    """
    df = v6_df.copy()
    
    # Rename columns
    df = df.rename(columns={
        'date': 'filing_date',
        'buyback_amount': 'amount_usd'
    })
    
    # Ensure required columns exist
    required = ['filing_date', 'ticker', 'amount_usd']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    return df[required + [c for c in df.columns if c not in required]]
