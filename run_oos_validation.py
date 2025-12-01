#!/usr/bin/env python3
"""
Out-of-Sample Validation
=========================
Fix look-ahead bias + Walk-forward backtest
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import matplotlib.pyplot as plt

# Import optimized engine
from optimized_backtest_engine import OptimizedBacktestEngine, calculate_metrics

BASE_DIR = Path(__file__).parent


def load_and_fix_sf1(reporting_delay_days=45):
    """Load SF1 data and fix look-ahead bias"""
    
    print(f"\n📂 Loading SF1 data...")
    sf1_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals.csv'
    sf1_df = pd.read_csv(sf1_file, parse_dates=['datekey', 'calendardate'])
    
    print(f"   Original records: {len(sf1_df)}")
    
    # Fix look-ahead bias: Add reporting delay
    sf1_df['datekey_adjusted'] = sf1_df['datekey'] + pd.Timedelta(days=reporting_delay_days)
    
    print(f"   Reporting delay: {reporting_delay_days} days")
    print(f"   datekey_adjusted = datekey + {reporting_delay_days} days")
    
    # Check lag after adjustment
    sf1_df['lag_days'] = (sf1_df['datekey_adjusted'] - sf1_df['calendardate']).dt.days
    
    negative_lag = sf1_df[sf1_df['lag_days'] < 0]
    
    print(f"\n🔍 After adjustment:")
    print(f"   Mean lag: {sf1_df['lag_days'].mean():.1f} days")
    print(f"   Median lag: {sf1_df['lag_days'].median():.1f} days")
    print(f"   Min lag: {sf1_df['lag_days'].min():.1f} days")
    print(f"   Negative lag records: {len(negative_lag)}")
    
    if len(negative_lag) > 0:
        print(f"   ⚠️  Still {len(negative_lag)} records with negative lag")
    else:
        print(f"   ✅ NO look-ahead bias!")
    
    # Use adjusted datekey for merging
    sf1_df['datekey'] = sf1_df['datekey_adjusted']
    sf1_df = sf1_df.drop(columns=['datekey_adjusted', 'lag_days'])
    
    return sf1_df


def merge_sf1_pit(stock_returns, sf1_df):
    """Point-in-time SF1 merge (fixed for look-ahead bias)"""
    
    print(f"\n🔗 Merging SF1 data (point-in-time, bias-free)...")
    
    dates = stock_returns.index
    symbols = stock_returns.columns
    n_dates = len(dates)
    n_symbols = len(symbols)
    
    # Convert to int64 for faster comparison
    dates_int = dates.values.astype('datetime64[D]').astype(np.int64)
    
    # Pre-allocate
    quality_matrix = np.full((n_dates, n_symbols), np.nan, dtype=np.float32)
    
    for j, ticker in enumerate(symbols):
        if j % 20 == 0:
            print(f"   Processing {j}/{n_symbols}...")
        
        ticker_sf1 = sf1_df[sf1_df['ticker'] == ticker].copy()
        
        if len(ticker_sf1) == 0:
            continue
        
        ticker_sf1 = ticker_sf1.sort_values('datekey')
        sf1_dates = ticker_sf1['datekey'].values.astype('datetime64[D]').astype(np.int64)
        
        # Quality scores
        roe = ticker_sf1['roe'].fillna(0.0).values
        ebitda_margin = ticker_sf1['ebitdamargin'].fillna(0.0).values
        de = ticker_sf1['de'].fillna(1.0).values
        
        quality_scores = 0.5 * roe + 0.3 * ebitda_margin - 0.2 * de
        
        # Point-in-time merge
        for i in range(n_dates):
            target_date = dates_int[i]
            
            # Find latest SF1 data where datekey <= target_date
            valid_idx = np.where(sf1_dates <= target_date)[0]
            
            if len(valid_idx) > 0:
                latest_idx = valid_idx[-1]
                quality_matrix[i, j] = quality_scores[latest_idx]
    
    quality_df = pd.DataFrame(
        quality_matrix,
        index=stock_returns.index,
        columns=stock_returns.columns
    )
    
    # Fill missing with median
    quality_df = quality_df.fillna(quality_df.median())
    
    coverage = quality_df.notna().sum().sum() / quality_df.size * 100
    print(f"   Coverage: {coverage:.1f}%")
    print(f"   ✅ Point-in-time merge complete!")
    
    return quality_df


def run_walk_forward_backtest():
    """Walk-forward backtest with train/OOS splits"""
    
    print("\n" + "="*80)
    print("Out-of-Sample Validation")
    print("="*80)
    
    # Load data
    print(f"\n📂 Loading baseline data...")
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
    
    # Stock returns
    prices_file = BASE_DIR / 'data' / 'prices.csv'
    df = pd.read_csv(prices_file)
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()
    
    prices = df.pivot(index='timestamp', columns='symbol', values='close')
    stock_returns = prices.pct_change().fillna(0.0)
    
    # Align dates
    common_dates = baseline_returns.index.intersection(stock_returns.index)
    baseline_returns = baseline_returns.loc[common_dates]
    stock_returns = stock_returns.loc[common_dates]
    
    print(f"   Total dates: {len(common_dates)}")
    print(f"   Start: {common_dates[0].date()}")
    print(f"   End: {common_dates[-1].date()}")
    
    # Load and fix SF1 data
    sf1_df = load_and_fix_sf1(reporting_delay_days=45)
    
    # Merge SF1 (point-in-time, bias-free)
    quality_df = merge_sf1_pit(stock_returns, sf1_df)
    
    # Define train/OOS splits
    splits = [
        {
            'name': 'Full Sample (In-Sample)',
            'start': '2015-11-25',
            'end': '2025-11-18',
            'type': 'train'
        },
        {
            'name': 'Train (2015-2019)',
            'start': '2015-11-25',
            'end': '2019-12-31',
            'type': 'train'
        },
        {
            'name': 'OOS 1 (2020-2021)',
            'start': '2020-01-01',
            'end': '2021-12-31',
            'type': 'oos'
        },
        {
            'name': 'OOS 2 (2022-2024)',
            'start': '2022-01-01',
            'end': '2024-12-31',
            'type': 'oos'
        },
        {
            'name': 'OOS 3 (2025)',
            'start': '2025-01-01',
            'end': '2025-11-18',
            'type': 'oos'
        }
    ]
    
    # Best config (from grid search)
    best_config = {
        'overlay_strength': 0.05,
        'top_frac': 0.20,
        'bottom_frac': 0.20
    }
    
    exposure_scale = 0.5392  # Balanced profile
    
    print(f"\n📊 Best Config:")
    print(f"   overlay_strength: {best_config['overlay_strength']}")
    print(f"   top_frac: {best_config['top_frac']}")
    print(f"   bottom_frac: {best_config['bottom_frac']}")
    print(f"   exposure_scale: {exposure_scale:.4f}")
    
    # Initialize engine
    engine = OptimizedBacktestEngine(train_window=2520)
    
    # Run backtest for each split
    results = {}
    
    print(f"\n" + "="*80)
    print("Running Walk-Forward Backtest...")
    print("="*80)
    
    for split in splits:
        print(f"\n📅 {split['name']}")
        print(f"   Period: {split['start']} to {split['end']}")
        print(f"   Type: {split['type'].upper()}")
        
        # Filter data
        start = pd.Timestamp(split['start'])
        end = pd.Timestamp(split['end'])
        
        mask = (stock_returns.index >= start) & (stock_returns.index <= end)
        split_stock_returns = stock_returns[mask]
        split_quality = quality_df[mask]
        split_baseline = baseline_returns[mask]
        
        if len(split_stock_returns) == 0:
            print(f"   ⚠️  No data in this period!")
            continue
        
        print(f"   Days: {len(split_stock_returns)}")
        
        # Run QM overlay backtest
        result = engine.run_qm_overlay_backtest(
            split_stock_returns,
            split_quality,
            **best_config
        )
        
        # Apply exposure scaling (Balanced profile)
        balanced_returns = result['returns'] * exposure_scale
        
        # Calculate metrics
        baseline_metrics = calculate_metrics(split_baseline)
        balanced_metrics = calculate_metrics(balanced_returns)
        
        results[split['name']] = {
            'type': split['type'],
            'period': f"{split['start']} to {split['end']}",
            'days': len(split_stock_returns),
            'baseline': {k: float(v) for k, v in baseline_metrics.items()},
            'balanced': {k: float(v) for k, v in balanced_metrics.items()}
        }
        
        print(f"\n   Baseline Sharpe: {baseline_metrics['sharpe']:.4f}")
        print(f"   Balanced Sharpe: {balanced_metrics['sharpe']:.4f}")
        print(f"   Delta: {balanced_metrics['sharpe'] - baseline_metrics['sharpe']:+.4f}")
    
    # Summary
    print(f"\n" + "="*80)
    print("Summary: Train vs OOS Performance")
    print("="*80)
    
    print(f"\n{'Period':<25} {'Type':<8} {'Days':<6} {'Baseline':<10} {'Balanced':<10} {'Delta':<10}")
    print("-" * 80)
    
    for name, res in results.items():
        baseline_sharpe = res['baseline']['sharpe']
        balanced_sharpe = res['balanced']['sharpe']
        delta = balanced_sharpe - baseline_sharpe
        
        print(f"{name:<25} {res['type'].upper():<8} {res['days']:<6} "
              f"{baseline_sharpe:>9.4f} {balanced_sharpe:>9.4f} {delta:>+9.4f}")
    
    # Overfitting check
    print(f"\n" + "="*80)
    print("Overfitting Analysis")
    print("="*80)
    
    train_sharpe = results['Train (2015-2019)']['balanced']['sharpe']
    oos_sharpes = [
        results['OOS 1 (2020-2021)']['balanced']['sharpe'],
        results['OOS 2 (2022-2024)']['balanced']['sharpe'],
        results['OOS 3 (2025)']['balanced']['sharpe']
    ]
    
    avg_oos_sharpe = np.mean(oos_sharpes)
    sharpe_degradation = train_sharpe - avg_oos_sharpe
    degradation_pct = sharpe_degradation / train_sharpe * 100
    
    print(f"\n📊 Sharpe Comparison:")
    print(f"   Train (2015-2019): {train_sharpe:.4f}")
    print(f"   OOS Average: {avg_oos_sharpe:.4f}")
    print(f"   Degradation: {sharpe_degradation:+.4f} ({degradation_pct:+.1f}%)")
    
    if abs(degradation_pct) < 10:
        print(f"   ✅ LOW overfitting (< 10% degradation)")
    elif abs(degradation_pct) < 20:
        print(f"   ⚠️  MODERATE overfitting (10-20% degradation)")
    else:
        print(f"   ❌ HIGH overfitting (> 20% degradation)")
    
    # Save results
    output_dir = BASE_DIR / 'tuning' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results_file = output_dir / 'oos_validation_results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✅ Results saved: {results_file}")
    
    print(f"\n" + "="*80)
    print("✅ Out-of-Sample Validation Complete!")
    print("="*80)
    
    return results


if __name__ == "__main__":
    results = run_walk_forward_backtest()
