#!/usr/bin/env python3
"""
Grid Search for QM Overlay Parameters
======================================
Find optimal overlay_strength, top_frac, bottom_frac
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import time
from itertools import product

# Import optimized engine
from optimized_backtest_engine import OptimizedBacktestEngine, calculate_metrics
from merge_sf1_optimized import merge_sf1_optimized

BASE_DIR = Path(__file__).parent


def load_data():
    """Load all required data"""
    
    print("📂 Loading data...")
    
    # Baseline returns
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
    
    # SF1 fundamentals
    sf1_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals.csv'
    sf1_df = pd.read_csv(sf1_file, parse_dates=['datekey', 'calendardate'])
    
    # Align dates
    common_dates = baseline_returns.index.intersection(stock_returns.index)
    baseline_returns = baseline_returns.loc[common_dates]
    stock_returns = stock_returns.loc[common_dates]
    
    print(f"   Dates: {len(common_dates)}")
    print(f"   Symbols: {len(stock_returns.columns)}")
    
    return baseline_returns, stock_returns, sf1_df, common_dates


def run_single_backtest(engine, stock_returns, quality_df, 
                       overlay_strength, top_frac, bottom_frac):
    """Run single backtest with given parameters"""
    
    qm_returns = engine.run_qm_overlay_backtest(
        stock_returns,
        quality_df,
        top_frac=top_frac,
        bottom_frac=bottom_frac,
        overlay_strength=overlay_strength
    )
    
    metrics = calculate_metrics(qm_returns['returns'])
    
    return metrics


def grid_search():
    """Run grid search for optimal parameters"""
    
    print("\n" + "="*80)
    print("Grid Search: QM Overlay Parameter Optimization")
    print("="*80)
    
    # Load data (once)
    baseline_returns, stock_returns, sf1_df, common_dates = load_data()
    
    # Merge SF1 data (once)
    print("\n🔗 Merging SF1 data...")
    quality_df = merge_sf1_optimized(stock_returns, sf1_df)
    
    # Initialize engine
    engine = OptimizedBacktestEngine(train_window=2520)
    
    # Define parameter grid
    param_grid = {
        'overlay_strength': [0.01, 0.02, 0.03, 0.04, 0.05],
        'top_frac': [0.10, 0.15, 0.20],
        'bottom_frac': [0.10, 0.15, 0.20]
    }
    
    # Generate all combinations
    param_combinations = list(product(
        param_grid['overlay_strength'],
        param_grid['top_frac'],
        param_grid['bottom_frac']
    ))
    
    total_combinations = len(param_combinations)
    
    print(f"\n📊 Grid Search Configuration:")
    print(f"   overlay_strength: {param_grid['overlay_strength']}")
    print(f"   top_frac: {param_grid['top_frac']}")
    print(f"   bottom_frac: {param_grid['bottom_frac']}")
    print(f"   Total combinations: {total_combinations}")
    
    # Baseline metrics
    baseline_metrics = calculate_metrics(baseline_returns)
    
    print(f"\n📊 Baseline Metrics:")
    print(f"   Sharpe: {baseline_metrics['sharpe']:.4f}")
    print(f"   Ann Vol: {baseline_metrics['ann_vol']*100:.2f}%")
    print(f"   Max DD: {baseline_metrics['max_dd']*100:.2f}%")
    
    # Run grid search
    print(f"\n🔍 Running Grid Search...")
    print(f"{'='*80}")
    
    results = []
    start_time = time.time()
    
    for i, (strength, top, bottom) in enumerate(param_combinations):
        iter_start = time.time()
        
        # Run backtest (suppress output)
        import sys
        from io import StringIO
        
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        
        try:
            metrics = run_single_backtest(
                engine, stock_returns, quality_df,
                strength, top, bottom
            )
        finally:
            sys.stdout = old_stdout
        
        iter_time = time.time() - iter_start
        
        # Store results
        result = {
            'overlay_strength': strength,
            'top_frac': top,
            'bottom_frac': bottom,
            'sharpe': metrics['sharpe'],
            'sortino': metrics['sortino'],
            'ann_return': metrics['ann_return'],
            'ann_vol': metrics['ann_vol'],
            'max_dd': metrics['max_dd'],
            'calmar': metrics['calmar'],
            'sharpe_delta': metrics['sharpe'] - baseline_metrics['sharpe'],
            'time': iter_time
        }
        
        results.append(result)
        
        # Progress
        progress = (i + 1) / total_combinations * 100
        eta = (time.time() - start_time) / (i + 1) * (total_combinations - i - 1)
        
        print(f"[{i+1:2d}/{total_combinations}] "
              f"strength={strength:.2f} top={top:.2f} bottom={bottom:.2f} | "
              f"Sharpe={metrics['sharpe']:.4f} (+{result['sharpe_delta']:+.4f}) "
              f"Vol={metrics['ann_vol']*100:5.2f}% DD={metrics['max_dd']*100:6.2f}% | "
              f"{iter_time:.2f}s | {progress:5.1f}% ETA={eta:.0f}s")
    
    total_time = time.time() - start_time
    
    print(f"\n{'='*80}")
    print(f"✅ Grid Search Complete!")
    print(f"   Total time: {total_time:.1f} seconds")
    print(f"   Avg time per run: {total_time / total_combinations:.2f} seconds")
    
    # Convert to DataFrame
    results_df = pd.DataFrame(results)
    
    # Find best parameters
    print(f"\n" + "="*80)
    print("🏆 Top 10 Configurations (by Sharpe)")
    print("="*80)
    
    # Filter by constraints
    filtered = results_df[
        (results_df['ann_vol'] < 0.15) &  # Vol < 15%
        (results_df['max_dd'] > -0.15)     # MDD > -15%
    ].copy()
    
    if len(filtered) == 0:
        print("⚠️  No configurations meet constraints (Vol<15%, MDD>-15%)")
        print("   Showing top 10 by Sharpe (unconstrained):")
        top_10 = results_df.nlargest(10, 'sharpe')
    else:
        print(f"✅ {len(filtered)} configurations meet constraints")
        top_10 = filtered.nlargest(10, 'sharpe')
    
    print(f"\n{'Rank':<5} {'Strength':<10} {'Top':<6} {'Bottom':<8} "
          f"{'Sharpe':<8} {'Δ Sharpe':<10} {'Vol':<8} {'MDD':<8}")
    print("-" * 80)
    
    for rank, (idx, row) in enumerate(top_10.iterrows(), 1):
        print(f"{rank:<5} {row['overlay_strength']:<10.2f} "
              f"{row['top_frac']:<6.2f} {row['bottom_frac']:<8.2f} "
              f"{row['sharpe']:<8.4f} {row['sharpe_delta']:<+10.4f} "
              f"{row['ann_vol']*100:<7.2f}% {row['max_dd']*100:<7.2f}%")
    
    # Best configuration
    best = top_10.iloc[0]
    
    print(f"\n" + "="*80)
    print("🎯 Best Configuration")
    print("="*80)
    print(f"   overlay_strength: {best['overlay_strength']:.2f}")
    print(f"   top_frac: {best['top_frac']:.2f}")
    print(f"   bottom_frac: {best['bottom_frac']:.2f}")
    print(f"\n   Sharpe: {best['sharpe']:.4f} (+{best['sharpe_delta']:+.4f})")
    print(f"   Sortino: {best['sortino']:.4f}")
    print(f"   Ann Return: {best['ann_return']*100:.2f}%")
    print(f"   Ann Vol: {best['ann_vol']*100:.2f}%")
    print(f"   Max DD: {best['max_dd']*100:.2f}%")
    print(f"   Calmar: {best['calmar']:.4f}")
    
    # Save results
    output_dir = BASE_DIR / 'tuning' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results_df.to_csv(output_dir / 'grid_search_results.csv', index=False)
    
    best_config = {
        'overlay_strength': float(best['overlay_strength']),
        'top_frac': float(best['top_frac']),
        'bottom_frac': float(best['bottom_frac']),
        'metrics': {
            'sharpe': float(best['sharpe']),
            'sortino': float(best['sortino']),
            'ann_return': float(best['ann_return']),
            'ann_vol': float(best['ann_vol']),
            'max_dd': float(best['max_dd']),
            'calmar': float(best['calmar'])
        },
        'baseline': {k: float(v) for k, v in baseline_metrics.items()}
    }
    
    with open(output_dir / 'best_qm_config.json', 'w') as f:
        json.dump(best_config, f, indent=2)
    
    print(f"\n✅ Results saved:")
    print(f"   {output_dir / 'grid_search_results.csv'}")
    print(f"   {output_dir / 'best_qm_config.json'}")
    
    return results_df, best_config


if __name__ == "__main__":
    results_df, best_config = grid_search()
