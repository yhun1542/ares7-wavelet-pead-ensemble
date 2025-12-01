#!/usr/bin/env python3
"""
Step 2: OOS 기반 Grid Search
============================
보수형 QM Overlay + OOS min Sharpe 기준 선택
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json

# Import optimized engine
from optimized_backtest_engine import OptimizedBacktestEngine, calculate_metrics

BASE_DIR = Path(__file__).parent


def merge_sf1_pit(stock_returns, sf1_df):
    """Point-in-time SF1 merge (90-day delay, bias-free)"""
    
    print(f"\n🔗 Merging SF1 data (point-in-time, 90-day delay)...")
    
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


def run_oos_grid_search():
    """Run Grid Search with OOS-based selection"""
    
    print("\n" + "="*80)
    print("Step 2: OOS 기반 Grid Search")
    print("="*80)
    
    # Load data
    print(f"\n📂 Loading data...")
    
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
    
    # Align dates
    common_dates = baseline_returns.index.intersection(stock_returns.index)
    baseline_returns = baseline_returns.loc[common_dates]
    stock_returns = stock_returns.loc[common_dates]
    
    print(f"   Total dates: {len(common_dates)}")
    print(f"   Start: {common_dates[0].date()}")
    print(f"   End: {common_dates[-1].date()}")
    
    # Load fixed SF1 data (90-day delay)
    sf1_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals_pit90d.csv'
    sf1_df = pd.read_csv(sf1_file, parse_dates=['datekey', 'calendardate'])
    
    print(f"   SF1 records: {len(sf1_df)}")
    
    # Merge SF1 (point-in-time, bias-free)
    quality_df = merge_sf1_pit(stock_returns, sf1_df)
    
    # Define train/OOS splits
    splits = {
        'train': ('2015-11-25', '2019-12-31'),
        'oos1': ('2020-01-01', '2021-12-31'),
        'oos2': ('2022-01-01', '2024-12-31'),
        'oos3': ('2025-01-01', '2025-11-18')
    }
    
    # Grid Search parameters (conservative)
    param_grid = {
        'overlay_strength': [0.02, 0.03, 0.04],
        'top_frac': [0.20],
        'bottom_frac': [0.20]
    }
    
    print(f"\n📊 Grid Search Parameters:")
    print(f"   overlay_strength: {param_grid['overlay_strength']}")
    print(f"   top_frac: {param_grid['top_frac']}")
    print(f"   bottom_frac: {param_grid['bottom_frac']}")
    print(f"   Total combinations: {len(param_grid['overlay_strength']) * len(param_grid['top_frac']) * len(param_grid['bottom_frac'])}")
    
    # Initialize engine
    engine = OptimizedBacktestEngine(train_window=2520)
    
    # Run Grid Search
    results = []
    
    print(f"\n" + "="*80)
    print("Running Grid Search...")
    print("="*80)
    
    for strength in param_grid['overlay_strength']:
        for top_frac in param_grid['top_frac']:
            for bottom_frac in param_grid['bottom_frac']:
                
                config = {
                    'overlay_strength': strength,
                    'top_frac': top_frac,
                    'bottom_frac': bottom_frac
                }
                
                print(f"\n📊 Config: strength={strength:.2f}, top={top_frac:.2f}, bottom={bottom_frac:.2f}")
                
                split_results = {}
                
                for split_name, (start, end) in splits.items():
                    start_date = pd.Timestamp(start)
                    end_date = pd.Timestamp(end)
                    
                    mask = (stock_returns.index >= start_date) & (stock_returns.index <= end_date)
                    split_stock_returns = stock_returns[mask]
                    split_quality = quality_df[mask]
                    split_baseline = baseline_returns[mask]
                    
                    if len(split_stock_returns) == 0:
                        continue
                    
                    # Run QM overlay backtest
                    result = engine.run_qm_overlay_backtest(
                        split_stock_returns,
                        split_quality,
                        **config
                    )
                    
                    # Calculate metrics
                    baseline_metrics = calculate_metrics(split_baseline)
                    overlay_metrics = calculate_metrics(result['returns'])
                    
                    split_results[split_name] = {
                        'baseline_sharpe': baseline_metrics['sharpe'],
                        'overlay_sharpe': overlay_metrics['sharpe'],
                        'delta_sharpe': overlay_metrics['sharpe'] - baseline_metrics['sharpe']
                    }
                    
                    print(f"   {split_name.upper()}: baseline={baseline_metrics['sharpe']:.4f}, "
                          f"overlay={overlay_metrics['sharpe']:.4f}, delta={split_results[split_name]['delta_sharpe']:+.4f}")
                
                # Calculate OOS score
                oos_sharpes = [
                    split_results['oos1']['overlay_sharpe'],
                    split_results['oos2']['overlay_sharpe'],
                    split_results['oos3']['overlay_sharpe']
                ]
                
                oos_min_sharpe = min(oos_sharpes)
                oos_avg_sharpe = np.mean(oos_sharpes)
                oos_std_sharpe = np.std(oos_sharpes)
                
                # Score = min(OOS Sharpe)
                score = oos_min_sharpe
                
                print(f"   OOS min Sharpe: {oos_min_sharpe:.4f}")
                print(f"   OOS avg Sharpe: {oos_avg_sharpe:.4f}")
                print(f"   OOS std Sharpe: {oos_std_sharpe:.4f}")
                print(f"   Score: {score:.4f}")
                
                results.append({
                    'config': config,
                    'train_sharpe': split_results['train']['overlay_sharpe'],
                    'oos1_sharpe': split_results['oos1']['overlay_sharpe'],
                    'oos2_sharpe': split_results['oos2']['overlay_sharpe'],
                    'oos3_sharpe': split_results['oos3']['overlay_sharpe'],
                    'oos_min_sharpe': oos_min_sharpe,
                    'oos_avg_sharpe': oos_avg_sharpe,
                    'oos_std_sharpe': oos_std_sharpe,
                    'score': score
                })
    
    # Sort by score (OOS min Sharpe)
    results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    # Summary
    print(f"\n" + "="*80)
    print("Grid Search Results (sorted by OOS min Sharpe)")
    print("="*80)
    
    print(f"\n{'Rank':<6} {'Strength':<10} {'Top':<6} {'Bottom':<8} {'Train':<8} {'OOS1':<8} {'OOS2':<8} {'OOS3':<8} {'Min':<8} {'Avg':<8} {'Score':<8}")
    print("-" * 120)
    
    for i, res in enumerate(results, 1):
        cfg = res['config']
        print(f"{i:<6} {cfg['overlay_strength']:<10.2f} {cfg['top_frac']:<6.2f} {cfg['bottom_frac']:<8.2f} "
              f"{res['train_sharpe']:<8.4f} {res['oos1_sharpe']:<8.4f} {res['oos2_sharpe']:<8.4f} {res['oos3_sharpe']:<8.4f} "
              f"{res['oos_min_sharpe']:<8.4f} {res['oos_avg_sharpe']:<8.4f} {res['score']:<8.4f}")
    
    # Best config
    best = results[0]
    
    print(f"\n" + "="*80)
    print("Best Config (OOS min Sharpe)")
    print("="*80)
    
    print(f"\n📊 Config:")
    print(f"   overlay_strength: {best['config']['overlay_strength']:.2f}")
    print(f"   top_frac: {best['config']['top_frac']:.2f}")
    print(f"   bottom_frac: {best['config']['bottom_frac']:.2f}")
    
    print(f"\n📈 Performance:")
    print(f"   Train Sharpe: {best['train_sharpe']:.4f}")
    print(f"   OOS 1 Sharpe: {best['oos1_sharpe']:.4f}")
    print(f"   OOS 2 Sharpe: {best['oos2_sharpe']:.4f}")
    print(f"   OOS 3 Sharpe: {best['oos3_sharpe']:.4f}")
    print(f"   OOS min Sharpe: {best['oos_min_sharpe']:.4f}")
    print(f"   OOS avg Sharpe: {best['oos_avg_sharpe']:.4f}")
    print(f"   Score: {best['score']:.4f}")
    
    # Save results
    output_dir = BASE_DIR / 'tuning' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results_file = output_dir / 'step2_oos_grid_search_results.json'
    with open(results_file, 'w') as f:
        json.dump({
            'grid_search_results': results,
            'best_config': best
        }, f, indent=2)
    
    print(f"\n✅ Results saved: {results_file}")
    
    print(f"\n" + "="*80)
    print("✅ Step 2 Complete: OOS 기반 Grid Search")
    print("="*80)
    
    return results, best


if __name__ == "__main__":
    results, best = run_oos_grid_search()
    print(f"\n📌 Next: Apply Global Exposure Scale to Best Config")
