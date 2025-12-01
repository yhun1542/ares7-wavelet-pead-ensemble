#!/usr/bin/env python3
"""
Phase 2: QM Overlay Backtest
=============================
Using optimized CPU engine with real SF1 data
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import matplotlib.pyplot as plt

# Import optimized engine
from optimized_backtest_engine import OptimizedBacktestEngine, calculate_metrics
from merge_sf1_optimized import merge_sf1_optimized

BASE_DIR = Path(__file__).parent


def load_ares7_data():
    """Load ARES7-Best baseline data"""
    
    print("📂 Loading ARES7-Best data...")
    
    # Load baseline returns
    baseline_file = BASE_DIR / 'results' / 'ares7_best_ensemble_results.json'
    with open(baseline_file) as f:
        baseline_data = json.load(f)
    
    # Parse daily_returns (list of dicts)
    dates = [item['date'] for item in baseline_data['daily_returns']]
    returns = [item['ret'] for item in baseline_data['daily_returns']]
    
    baseline_returns = pd.Series(
        returns,
        index=pd.to_datetime(dates),
        name='baseline'
    )
    
    print(f"   Baseline: {len(baseline_returns)} days")
    
    return baseline_returns


def load_stock_returns():
    """Load individual stock returns from prices.csv"""
    
    print("📂 Loading stock returns...")
    
    prices_file = BASE_DIR / 'data' / 'prices.csv'
    df = pd.read_csv(prices_file)
    
    # Convert to datetime and normalize to date only
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()
    
    # Pivot to wide format
    prices = df.pivot(index='timestamp', columns='symbol', values='close')
    
    # Calculate returns
    returns = prices.pct_change().fillna(0.0)
    
    print(f"   Returns: {returns.shape}")
    print(f"   Dates: {len(returns)}")
    print(f"   Symbols: {len(returns.columns)}")
    
    return returns


def load_sf1_fundamentals():
    """Load SF1 fundamentals data"""
    
    print("📂 Loading SF1 fundamentals...")
    
    sf1_file = BASE_DIR / 'data' / 'ares7_sf1_fundamentals.csv'
    df = pd.read_csv(sf1_file, parse_dates=['datekey', 'calendardate'])
    
    print(f"   SF1 records: {len(df)}")
    print(f"   Tickers: {df['ticker'].nunique()}")
    
    return df


def merge_sf1_to_returns(returns_df, sf1_df):
    """Merge SF1 data to returns with point-in-time alignment"""
    
    print("\n🔗 Merging SF1 data to returns...")
    
    # Create quality DataFrame aligned with returns
    quality_data = {}
    
    for ticker in returns_df.columns:
        ticker_sf1 = sf1_df[sf1_df['ticker'] == ticker].copy()
        
        if len(ticker_sf1) == 0:
            continue
        
        ticker_sf1 = ticker_sf1.sort_values('datekey')
        
        # Merge asof (point-in-time)
        quality_series = pd.Series(index=returns_df.index, dtype=float)
        
        for date in returns_df.index:
            # Find most recent SF1 data before this date
            available = ticker_sf1[ticker_sf1['datekey'] <= date]
            
            if len(available) > 0:
                latest = available.iloc[-1]
                
                # Composite quality score
                roe = latest['roe'] if not pd.isna(latest['roe']) else 0.0
                ebitda_margin = latest['ebitdamargin'] if not pd.isna(latest['ebitdamargin']) else 0.0
                de = latest['de'] if not pd.isna(latest['de']) else 1.0
                
                # Quality score
                quality = 0.5 * roe + 0.3 * ebitda_margin - 0.2 * de
                quality_series.loc[date] = quality
        
        quality_data[ticker] = quality_series
    
    quality_df = pd.DataFrame(quality_data)
    
    # Fill missing with median
    quality_df = quality_df.fillna(quality_df.median())
    
    print(f"   Quality data shape: {quality_df.shape}")
    print(f"   Coverage: {quality_df.notna().sum().sum() / quality_df.size * 100:.1f}%")
    
    return quality_df


def run_phase2_backtest():
    """Run Phase 2: QM Overlay backtest"""
    
    print("\n" + "="*80)
    print("Phase 2: QM Overlay Backtest")
    print("="*80)
    
    # Load data
    baseline_returns = load_ares7_data()
    stock_returns = load_stock_returns()
    sf1_df = load_sf1_fundamentals()
    
    # Align dates
    common_dates = baseline_returns.index.intersection(stock_returns.index)
    baseline_returns = baseline_returns.loc[common_dates]
    stock_returns = stock_returns.loc[common_dates]
    
    print(f"\n📅 Common dates: {len(common_dates)}")
    print(f"   Start: {common_dates[0].date()}")
    print(f"   End: {common_dates[-1].date()}")
    
    # Merge SF1 data (OPTIMIZED)
    quality_df = merge_sf1_optimized(stock_returns, sf1_df)
    
    # Initialize optimized engine
    engine = OptimizedBacktestEngine(train_window=2520)
    
    # Run QM Overlay backtest
    print("\n" + "="*80)
    print("Running QM Overlay Backtest...")
    print("="*80)
    
    qm_returns = engine.run_qm_overlay_backtest(
        stock_returns,
        quality_df,
        top_frac=0.10,
        bottom_frac=0.10,
        overlay_strength=0.05  # 0.15 → 0.05 (보수형)
    )
    
    # Align results
    qm_returns = qm_returns.loc[common_dates]
    
    # Calculate metrics
    print("\n" + "="*80)
    print("Performance Comparison")
    print("="*80)
    
    baseline_metrics = calculate_metrics(baseline_returns)
    qm_metrics = calculate_metrics(qm_returns['returns'])
    
    print("\n📊 Baseline (ARES7-Best):")
    for k, v in baseline_metrics.items():
        print(f"   {k:12s}: {v:8.4f}")
    
    print("\n📊 QM Overlay:")
    for k, v in qm_metrics.items():
        print(f"   {k:12s}: {v:8.4f}")
    
    print("\n📈 Delta:")
    for k in baseline_metrics.keys():
        delta = qm_metrics[k] - baseline_metrics[k]
        pct = (delta / baseline_metrics[k] * 100) if baseline_metrics[k] != 0 else 0
        print(f"   Δ {k:12s}: {delta:+8.4f} ({pct:+6.2f}%)")
    
    # Save results
    output_dir = BASE_DIR / 'tuning' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert numpy types to Python types for JSON serialization
    results = {
        'baseline': {k: float(v) for k, v in baseline_metrics.items()},
        'qm_overlay': {k: float(v) for k, v in qm_metrics.items()},
        'delta': {k: float(qm_metrics[k] - baseline_metrics[k]) for k in baseline_metrics.keys()}
    }
    
    with open(output_dir / 'phase2_qm_overlay_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save returns
    combined = pd.DataFrame({
        'baseline': baseline_returns,
        'qm_overlay': qm_returns['returns']
    })
    combined.to_csv(output_dir / 'phase2_qm_overlay_returns.csv')
    
    # Plot
    print("\n📊 Generating plot...")
    
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    
    # Cumulative returns
    cum_baseline = (1 + baseline_returns).cumprod()
    cum_qm = (1 + qm_returns['returns']).cumprod()
    
    axes[0].plot(cum_baseline.index, cum_baseline.values, label='Baseline', linewidth=2)
    axes[0].plot(cum_qm.index, cum_qm.values, label='QM Overlay', linewidth=2)
    axes[0].set_title('Cumulative Returns', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('Cumulative Return')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Rolling Sharpe
    rolling_sharpe_baseline = baseline_returns.rolling(252).apply(
        lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0
    )
    rolling_sharpe_qm = qm_returns['returns'].rolling(252).apply(
        lambda x: x.mean() / x.std() * np.sqrt(252) if x.std() > 0 else 0
    )
    
    axes[1].plot(rolling_sharpe_baseline.index, rolling_sharpe_baseline.values, 
                 label='Baseline', linewidth=2)
    axes[1].plot(rolling_sharpe_qm.index, rolling_sharpe_qm.values,
                 label='QM Overlay', linewidth=2)
    axes[1].set_title('Rolling 252-Day Sharpe Ratio', fontsize=14, fontweight='bold')
    axes[1].set_ylabel('Sharpe Ratio')
    axes[1].set_xlabel('Date')
    axes[1].legend()
    axes[1].grid(True, alpha=0.3)
    axes[1].axhline(y=2.0, color='red', linestyle='--', alpha=0.5, label='Target 2.0')
    
    plt.tight_layout()
    plt.savefig(output_dir / 'phase2_qm_overlay_plot.png', dpi=150, bbox_inches='tight')
    
    print(f"   Saved: {output_dir / 'phase2_qm_overlay_plot.png'}")
    
    print("\n" + "="*80)
    print("✅ Phase 2 Complete!")
    print("="*80)
    
    return results


if __name__ == "__main__":
    results = run_phase2_backtest()
