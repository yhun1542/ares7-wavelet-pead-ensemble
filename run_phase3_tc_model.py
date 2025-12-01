#!/usr/bin/env python3
"""
Phase 3: Transaction Cost Model Backtest
=========================================
Optimize trading costs with spread/ADV/volatility model
"""

import pandas as pd
import numpy as np
from pathlib import Path
import json
import matplotlib.pyplot as plt
from numba import njit, prange

# Import optimized engine
from optimized_backtest_engine import calculate_metrics

BASE_DIR = Path(__file__).parent


@njit(parallel=True, cache=True, fastmath=True)
def compute_transaction_costs_numba(weights_prev, weights_curr, volumes, prices, volatilities):
    """
    Compute transaction costs with Numba JIT
    
    TC = sum(|delta_weight| * (spread + impact))
    spread = k1 * volatility
    impact = k2 * |trade_size| / ADV
    """
    
    n_symbols = len(weights_curr)
    total_cost = 0.0
    
    # Cost parameters
    k_spread = 0.0005  # 5 bps base spread
    k_impact = 0.001   # Impact coefficient
    k_vol = 0.01       # Volatility multiplier
    
    for i in prange(n_symbols):
        # Weight change
        delta_w = abs(weights_curr[i] - weights_prev[i])
        
        if delta_w > 1e-6:  # Only if there's a trade
            # Spread cost (volatility-based)
            spread = k_spread + k_vol * volatilities[i]
            
            # Market impact (volume-based)
            adv = volumes[i] * prices[i]  # Average Dollar Volume
            trade_size = delta_w * 1e6  # Assume $1M portfolio
            
            if adv > 0:
                impact = k_impact * (trade_size / adv) ** 0.5
            else:
                impact = k_impact
            
            # Total cost for this symbol
            cost = delta_w * (spread + impact)
            total_cost += cost
    
    return total_cost


class TransactionCostModel:
    """Transaction Cost Model with optimization"""
    
    def __init__(self, max_turnover=0.50, rebalance_threshold=0.05):
        """
        Args:
            max_turnover: Maximum daily turnover (50% default)
            rebalance_threshold: Minimum weight change to trigger rebalance (5% default)
        """
        self.max_turnover = max_turnover
        self.rebalance_threshold = rebalance_threshold
    
    def apply_tc_optimization(self, weights_df, volumes_df, prices_df, returns_df):
        """
        Apply transaction cost optimization to weights
        
        Returns:
            optimized_weights_df: Adjusted weights
            costs_series: Daily transaction costs
        """
        
        print("\n🔧 Applying Transaction Cost Optimization...")
        print(f"   Max turnover: {self.max_turnover * 100:.1f}%")
        print(f"   Rebalance threshold: {self.rebalance_threshold * 100:.1f}%")
        
        dates = weights_df.index
        symbols = weights_df.columns
        
        optimized_weights = []
        daily_costs = []
        
        # Calculate rolling volatility
        volatilities = returns_df.rolling(20).std().fillna(0.01)
        
        prev_weights = np.zeros(len(symbols))
        
        for i, date in enumerate(dates):
            if i % 100 == 0:
                print(f"   Processing {i}/{len(dates)}...")
            
            # Target weights
            target_weights = weights_df.loc[date].values
            
            # Current volumes and prices
            volumes = volumes_df.loc[date].values if date in volumes_df.index else np.ones(len(symbols))
            prices = prices_df.loc[date].values if date in prices_df.index else np.ones(len(symbols))
            vols = volatilities.loc[date].values if date in volatilities.index else np.ones(len(symbols)) * 0.01
            
            # Check if rebalance is needed
            weight_changes = np.abs(target_weights - prev_weights)
            max_change = np.max(weight_changes)
            
            if max_change < self.rebalance_threshold:
                # Skip rebalance
                current_weights = prev_weights.copy()
                cost = 0.0
            else:
                # Compute transaction cost
                cost = compute_transaction_costs_numba(
                    prev_weights, target_weights, volumes, prices, vols
                )
                
                # Check turnover constraint
                turnover = np.sum(weight_changes)
                
                if turnover > self.max_turnover:
                    # Scale down changes
                    scale = self.max_turnover / turnover
                    current_weights = prev_weights + scale * (target_weights - prev_weights)
                else:
                    current_weights = target_weights.copy()
            
            optimized_weights.append(current_weights)
            daily_costs.append(cost)
            prev_weights = current_weights.copy()
        
        # Convert to DataFrame
        optimized_weights_df = pd.DataFrame(
            optimized_weights,
            index=dates,
            columns=symbols
        )
        
        costs_series = pd.Series(daily_costs, index=dates, name='tc_costs')
        
        print(f"\n✅ TC Optimization Complete!")
        print(f"   Avg daily cost: {costs_series.mean() * 10000:.2f} bps")
        print(f"   Total cost: {costs_series.sum() * 100:.2f}%")
        
        return optimized_weights_df, costs_series


def load_baseline_data():
    """Load baseline data"""
    
    print("📂 Loading baseline data...")
    
    # Load baseline returns
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
    
    print(f"   Baseline: {len(baseline_returns)} days")
    
    return baseline_returns


def load_stock_data():
    """Load stock prices and volumes"""
    
    print("📂 Loading stock data...")
    
    prices_file = BASE_DIR / 'data' / 'prices.csv'
    df = pd.read_csv(prices_file)
    
    df['timestamp'] = pd.to_datetime(df['timestamp']).dt.normalize()
    
    # Pivot
    prices = df.pivot(index='timestamp', columns='symbol', values='close')
    volumes = df.pivot(index='timestamp', columns='symbol', values='volume')
    
    # Returns
    returns = prices.pct_change().fillna(0.0)
    
    print(f"   Prices: {prices.shape}")
    print(f"   Volumes: {volumes.shape}")
    
    return prices, volumes, returns


def run_phase3_backtest():
    """Run Phase 3: TC Model backtest"""
    
    print("\n" + "="*80)
    print("Phase 3: Transaction Cost Model Backtest")
    print("="*80)
    
    # Load data
    baseline_returns = load_baseline_data()
    prices, volumes, stock_returns = load_stock_data()
    
    # Align dates
    common_dates = baseline_returns.index.intersection(stock_returns.index)
    baseline_returns = baseline_returns.loc[common_dates]
    stock_returns = stock_returns.loc[common_dates]
    prices = prices.loc[common_dates]
    volumes = volumes.loc[common_dates]
    
    print(f"\n📅 Common dates: {len(common_dates)}")
    print(f"   Start: {common_dates[0].date()}")
    print(f"   End: {common_dates[-1].date()}")
    
    # Create baseline weights (equal weight for simplicity)
    baseline_weights = pd.DataFrame(
        np.ones((len(common_dates), len(stock_returns.columns))) / len(stock_returns.columns),
        index=common_dates,
        columns=stock_returns.columns
    )
    
    # Initialize TC Model
    tc_model = TransactionCostModel(
        max_turnover=0.50,
        rebalance_threshold=0.05
    )
    
    # Apply TC optimization
    optimized_weights, tc_costs = tc_model.apply_tc_optimization(
        baseline_weights,
        volumes,
        prices,
        stock_returns
    )
    
    # Compute portfolio returns (before and after TC)
    print("\n💰 Computing portfolio returns...")
    
    # Before TC
    portfolio_returns_before = (baseline_weights * stock_returns).sum(axis=1)
    
    # After TC
    portfolio_returns_after = (optimized_weights * stock_returns).sum(axis=1) - tc_costs
    
    # Calculate metrics
    print("\n" + "="*80)
    print("Performance Comparison")
    print("="*80)
    
    baseline_metrics = calculate_metrics(baseline_returns)
    before_tc_metrics = calculate_metrics(portfolio_returns_before)
    after_tc_metrics = calculate_metrics(portfolio_returns_after)
    
    print("\n📊 Baseline (ARES7-Best):")
    for k, v in baseline_metrics.items():
        print(f"   {k:12s}: {v:8.4f}")
    
    print("\n📊 Before TC Optimization:")
    for k, v in before_tc_metrics.items():
        print(f"   {k:12s}: {v:8.4f}")
    
    print("\n📊 After TC Optimization:")
    for k, v in after_tc_metrics.items():
        print(f"   {k:12s}: {v:8.4f}")
    
    print("\n📈 Delta (After TC vs Baseline):")
    for k in baseline_metrics.keys():
        delta = after_tc_metrics[k] - baseline_metrics[k]
        pct = (delta / baseline_metrics[k] * 100) if baseline_metrics[k] != 0 else 0
        print(f"   Δ {k:12s}: {delta:+8.4f} ({pct:+6.2f}%)")
    
    # Save results
    output_dir = BASE_DIR / 'tuning' / 'results'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    results = {
        'baseline': baseline_metrics,
        'before_tc': before_tc_metrics,
        'after_tc': after_tc_metrics,
        'delta': {k: after_tc_metrics[k] - baseline_metrics[k] for k in baseline_metrics.keys()},
        'avg_daily_tc_bps': float(tc_costs.mean() * 10000),
        'total_tc_pct': float(tc_costs.sum() * 100)
    }
    
    with open(output_dir / 'phase3_tc_model_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    
    # Save returns
    combined = pd.DataFrame({
        'baseline': baseline_returns,
        'before_tc': portfolio_returns_before,
        'after_tc': portfolio_returns_after,
        'tc_costs': tc_costs
    })
    combined.to_csv(output_dir / 'phase3_tc_model_returns.csv')
    
    # Plot
    print("\n📊 Generating plot...")
    
    fig, axes = plt.subplots(3, 1, figsize=(12, 10))
    
    # Cumulative returns
    cum_baseline = (1 + baseline_returns).cumprod()
    cum_before = (1 + portfolio_returns_before).cumprod()
    cum_after = (1 + portfolio_returns_after).cumprod()
    
    axes[0].plot(cum_baseline.index, cum_baseline.values, label='Baseline', linewidth=2)
    axes[0].plot(cum_before.index, cum_before.values, label='Before TC', linewidth=2, alpha=0.7)
    axes[0].plot(cum_after.index, cum_after.values, label='After TC', linewidth=2)
    axes[0].set_title('Cumulative Returns', fontsize=14, fontweight='bold')
    axes[0].set_ylabel('Cumulative Return')
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)
    
    # Transaction costs
    axes[1].plot(tc_costs.index, tc_costs.values * 10000, linewidth=1)
    axes[1].set_title('Daily Transaction Costs', fontsize=14, fontweight='bold')
    axes[1].set_ylabel('Cost (bps)')
    axes[1].grid(True, alpha=0.3)
    
    # Cumulative TC impact
    cum_tc = tc_costs.cumsum()
    axes[2].plot(cum_tc.index, cum_tc.values * 100, linewidth=2, color='red')
    axes[2].set_title('Cumulative Transaction Costs', fontsize=14, fontweight='bold')
    axes[2].set_ylabel('Cumulative Cost (%)')
    axes[2].set_xlabel('Date')
    axes[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_dir / 'phase3_tc_model_plot.png', dpi=150, bbox_inches='tight')
    
    print(f"   Saved: {output_dir / 'phase3_tc_model_plot.png'}")
    
    print("\n" + "="*80)
    print("✅ Phase 3 Complete!")
    print("="*80)
    
    return results


if __name__ == "__main__":
    results = run_phase3_backtest()
