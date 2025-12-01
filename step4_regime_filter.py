#!/usr/bin/env python3
"""
Step 4: 레짐 필터 구현
======================
BULL 레짐에서만 QM Overlay 적용
"""

import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).parent


def compute_bull_regime(spx_prices):
    """
    Compute BULL regime based on hard conditions
    
    BULL 조건 (모두 만족 시에만 overlay 적용):
    1) SPX > 200일 이동평균
    2) SPX 6개월 수익률 > 0
    3) SPX 12개월 수익률 > 0
    4) VIX < 25
    
    Parameters
    ----------
    spx_prices : pd.Series
        SPX close prices (daily)
    
    Returns
    -------
    bull_regime : pd.Series (bool)
        True if BULL regime, False otherwise
    """
    
    # 1) SPX > 200-day MA
    ma200 = spx_prices.rolling(200).mean()
    cond1 = spx_prices > ma200
    
    # 2) SPX 6-month return > 0
    ret_6m = spx_prices.pct_change(126)  # ~6 months
    cond2 = ret_6m > 0
    
    # 3) SPX 12-month return > 0
    ret_12m = spx_prices.pct_change(252)  # ~12 months
    cond3 = ret_12m > 0
    
    # 4) VIX < 25 (placeholder - will be loaded separately)
    # For now, we'll compute this in the main script
    
    # Combine conditions 1, 2, 3
    bull_regime = cond1 & cond2 & cond3
    
    return bull_regime


def load_vix_data():
    """Load VIX data from FRED"""
    
    vix_file = BASE_DIR / 'data' / 'vix_data.csv'
    
    if not vix_file.exists():
        print(f"⚠️  VIX data not found: {vix_file}")
        print(f"   Using dummy VIX data (all < 25)")
        return None
    
    vix_df = pd.read_csv(vix_file, parse_dates=['date'])
    vix_df = vix_df.set_index('date')['vix_close']
    
    return vix_df


def compute_full_bull_regime(spx_prices, vix_data=None):
    """
    Compute BULL regime with all 4 conditions
    
    Parameters
    ----------
    spx_prices : pd.Series
        SPX close prices (daily)
    vix_data : pd.Series, optional
        VIX close prices (daily)
    
    Returns
    -------
    bull_regime : pd.Series (bool)
        True if BULL regime, False otherwise
    stats : dict
        Regime statistics
    """
    
    print("\n" + "="*80)
    print("Computing BULL Regime")
    print("="*80)
    
    # Conditions 1, 2, 3
    ma200 = spx_prices.rolling(200).mean()
    cond1 = spx_prices > ma200
    
    ret_6m = spx_prices.pct_change(126)
    cond2 = ret_6m > 0
    
    ret_12m = spx_prices.pct_change(252)
    cond3 = ret_12m > 0
    
    # Condition 4: VIX < 25
    if vix_data is not None:
        # Align VIX data with SPX dates
        vix_aligned = vix_data.reindex(spx_prices.index, method='ffill')
        cond4 = vix_aligned < 25
    else:
        # Dummy: assume VIX always < 25
        print(f"⚠️  Using dummy VIX condition (always True)")
        cond4 = pd.Series(True, index=spx_prices.index)
    
    # Combine all conditions
    bull_regime = cond1 & cond2 & cond3 & cond4
    
    # Statistics
    total_days = len(bull_regime)
    bull_days = bull_regime.sum()
    bull_pct = bull_days / total_days * 100
    
    # Condition breakdown
    cond1_pct = cond1.sum() / total_days * 100
    cond2_pct = cond2.sum() / total_days * 100
    cond3_pct = cond3.sum() / total_days * 100
    cond4_pct = cond4.sum() / total_days * 100
    
    print(f"\n📊 Regime Statistics:")
    print(f"   Total days: {total_days}")
    print(f"   BULL days: {bull_days} ({bull_pct:.1f}%)")
    print(f"   BEAR/HIGH_VOL days: {total_days - bull_days} ({100 - bull_pct:.1f}%)")
    
    print(f"\n📋 Condition Breakdown:")
    print(f"   1) SPX > MA200: {cond1.sum()} ({cond1_pct:.1f}%)")
    print(f"   2) 6M ret > 0: {cond2.sum()} ({cond2_pct:.1f}%)")
    print(f"   3) 12M ret > 0: {cond3.sum()} ({cond3_pct:.1f}%)")
    print(f"   4) VIX < 25: {cond4.sum()} ({cond4_pct:.1f}%)")
    
    # Period analysis
    print(f"\n📅 Period Analysis:")
    
    splits = {
        'Train (2015-2019)': ('2015-11-25', '2019-12-31'),
        'OOS 1 (2020-2021)': ('2020-01-01', '2021-12-31'),
        'OOS 2 (2022-2024)': ('2022-01-01', '2024-12-31'),
        'OOS 3 (2025)': ('2025-01-01', '2025-11-18')
    }
    
    period_stats = {}
    
    for period_name, (start, end) in splits.items():
        start_date = pd.Timestamp(start)
        end_date = pd.Timestamp(end)
        
        mask = (bull_regime.index >= start_date) & (bull_regime.index <= end_date)
        period_regime = bull_regime[mask]
        
        if len(period_regime) == 0:
            continue
        
        period_bull_pct = period_regime.sum() / len(period_regime) * 100
        period_stats[period_name] = period_bull_pct
        
        print(f"   {period_name}: {period_regime.sum()}/{len(period_regime)} ({period_bull_pct:.1f}%) BULL")
    
    stats = {
        'total_days': total_days,
        'bull_days': int(bull_days),
        'bull_pct': float(bull_pct),
        'cond1_pct': float(cond1_pct),
        'cond2_pct': float(cond2_pct),
        'cond3_pct': float(cond3_pct),
        'cond4_pct': float(cond4_pct),
        'period_stats': period_stats
    }
    
    print(f"\n" + "="*80)
    print("✅ BULL Regime Computed")
    print("="*80)
    
    return bull_regime, stats


if __name__ == "__main__":
    print("\n" + "="*80)
    print("Step 4: 레짐 필터 구현 (BULL 조건)")
    print("="*80)
    
    # Load SPX prices (from ARES7-Best baseline)
    print(f"\n📂 Loading SPX proxy data...")
    
    # Use ARES7-Best baseline as SPX proxy
    import json
    
    baseline_file = BASE_DIR / 'results' / 'ares7_best_ensemble_results.json'
    with open(baseline_file) as f:
        baseline_data = json.load(f)
    
    dates = [item['date'] for item in baseline_data['daily_returns']]
    returns = [item['ret'] for item in baseline_data['daily_returns']]
    
    baseline_returns = pd.Series(
        returns,
        index=pd.to_datetime(dates),
        name='baseline'
    )
    
    # Convert returns to prices (cumulative)
    spx_proxy = (1 + baseline_returns).cumprod() * 100
    
    print(f"   Dates: {len(spx_proxy)}")
    print(f"   Start: {spx_proxy.index[0].date()}")
    print(f"   End: {spx_proxy.index[-1].date()}")
    
    # Load VIX data
    vix_data = load_vix_data()
    
    # Compute BULL regime
    bull_regime, stats = compute_full_bull_regime(spx_proxy, vix_data)
    
    # Save regime data
    output_dir = BASE_DIR / 'data'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    regime_file = output_dir / 'bull_regime.csv'
    bull_regime.to_csv(regime_file, header=True)
    
    print(f"\n✅ Regime data saved: {regime_file}")
    
    # Save stats
    stats_file = output_dir / 'bull_regime_stats.json'
    with open(stats_file, 'w') as f:
        json.dump(stats, f, indent=2)
    
    print(f"✅ Stats saved: {stats_file}")
    
    print(f"\n📌 Next: Use bull_regime.csv for Grid Search with regime filter")
