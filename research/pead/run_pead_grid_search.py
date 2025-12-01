#!/usr/bin/env python3
"""
PEAD v1 Grid Search Optimization
=================================

Optimize PEAD parameters to maximize Net Incremental Sharpe Ratio.

Parameters to optimize:
- budget: [0.02, 0.05, 0.10]
- horizon: [5, 10, 15, 20]
- transaction_cost: [0.0005, 0.001]

Base: Volatility-Weighted Portfolio
Metric: Net Incremental Sharpe (after transaction costs)

Usage:
    python -m research.pead.run_pead_grid_search
"""

import os
import sys
import pandas as pd
import numpy as np
from itertools import product
from datetime import datetime
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from research.pead.config import (
    PRICES_PATHS,
    EPS_TABLE_PATH,
    BASE_WEIGHTS_PATH,
)
from research.pead.event_table_builder_v1 import build_eps_events
from research.pead.overlay_engine import OverlayEngine


# Output directory
OUTPUT_DIR = '/home/ubuntu/ares7-ensemble/results/pead_grid_search'
os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_single_config(budget, horizon, transaction_cost):
    """
    Run PEAD overlay with a single parameter configuration.
    
    Returns:
        dict with keys: budget, horizon, tc, train_sharpe, val_sharpe, test_sharpe, 
                        train_incr_sharpe, val_incr_sharpe, test_incr_sharpe
    """
    print(f"\n{'='*80}")
    print(f"Config: budget={budget:.1%}, horizon={horizon}d, tc={transaction_cost:.2%}")
    print(f"{'='*80}")
    
    try:
        # Build event table
        print("Building event table...")
        event_df = build_eps_events(EPS_TABLE_PATH, PRICES_PATHS)
        
        # Initialize overlay engine
        engine = OverlayEngine(
            event_df=event_df,
            price_paths=PRICES_PATHS,
            base_weights_path=BASE_WEIGHTS_PATH,
            budget=budget,
            horizon=horizon,
            transaction_cost=transaction_cost,
        )
        
        # Run backtest
        print("Running backtest...")
        results = engine.run()
        
        # Extract metrics
        metrics = {
            'budget': budget,
            'horizon': horizon,
            'transaction_cost': transaction_cost,
        }
        
        # Period metrics
        for period in ['train', 'val', 'test', 'full']:
            period_stats = results.get(f'{period}_stats', {})
            
            metrics[f'{period}_sharpe'] = period_stats.get('sharpe', np.nan)
            metrics[f'{period}_base_sharpe'] = period_stats.get('base_sharpe', np.nan)
            metrics[f'{period}_incr_sharpe'] = period_stats.get('incremental_sharpe', np.nan)
            metrics[f'{period}_annual_return'] = period_stats.get('annual_return', np.nan)
            metrics[f'{period}_annual_vol'] = period_stats.get('annual_volatility', np.nan)
            metrics[f'{period}_max_dd'] = period_stats.get('max_drawdown', np.nan)
            metrics[f'{period}_turnover'] = period_stats.get('annual_turnover', np.nan)
        
        # Print summary
        print("\nResults Summary:")
        print(f"  Train Incremental Sharpe: {metrics['train_incr_sharpe']:.3f}")
        print(f"  Val Incremental Sharpe:   {metrics['val_incr_sharpe']:.3f}")
        print(f"  Test Incremental Sharpe:  {metrics['test_incr_sharpe']:.3f}")
        print(f"  Full Incremental Sharpe:  {metrics['full_incr_sharpe']:.3f}")
        print(f"  Val Turnover:             {metrics['val_turnover']:.1%}")
        
        return metrics
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'budget': budget,
            'horizon': horizon,
            'transaction_cost': transaction_cost,
            'error': str(e),
        }


def main():
    """Main grid search execution"""
    print("=" * 80)
    print("PEAD v1 Grid Search Optimization")
    print("=" * 80)
    print()
    print(f"Base Weights: {BASE_WEIGHTS_PATH}")
    print(f"EPS Data: {EPS_TABLE_PATH}")
    print()
    
    # Grid search parameters
    budgets = [0.02, 0.05, 0.10]
    horizons = [5, 10, 15, 20]
    transaction_costs = [0.0005, 0.001]
    
    print("Grid Search Space:")
    print(f"  Budgets: {[f'{b:.1%}' for b in budgets]}")
    print(f"  Horizons: {horizons}")
    print(f"  Transaction Costs: {[f'{tc:.2%}' for tc in transaction_costs]}")
    print(f"  Total Configurations: {len(budgets) * len(horizons) * len(transaction_costs)}")
    print()
    
    # Run grid search
    results = []
    
    for i, (budget, horizon, tc) in enumerate(product(budgets, horizons, transaction_costs), 1):
        print(f"\n[{i}/{len(budgets) * len(horizons) * len(transaction_costs)}]")
        
        metrics = run_single_config(budget, horizon, tc)
        results.append(metrics)
        
        # Save intermediate results
        df = pd.DataFrame(results)
        df.to_csv(f'{OUTPUT_DIR}/grid_search_results_temp.csv', index=False)
    
    # Final results
    df = pd.DataFrame(results)
    
    # Sort by validation incremental Sharpe (primary metric)
    df = df.sort_values('val_incr_sharpe', ascending=False)
    
    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'{OUTPUT_DIR}/grid_search_results_{timestamp}.csv'
    df.to_csv(output_file, index=False)
    
    # Summary
    print()
    print("=" * 80)
    print("Grid Search Complete")
    print("=" * 80)
    print()
    print(f"Results saved to: {output_file}")
    print()
    
    # Top 5 configurations
    print("Top 5 Configurations (by Validation Incremental Sharpe):")
    print("-" * 80)
    
    top5 = df.head(5)
    for i, row in top5.iterrows():
        print(f"\n{i+1}. Budget={row['budget']:.1%}, Horizon={row['horizon']:.0f}d, TC={row['transaction_cost']:.2%}")
        print(f"   Val Incr Sharpe: {row['val_incr_sharpe']:.3f}")
        print(f"   Test Incr Sharpe: {row['test_incr_sharpe']:.3f}")
        print(f"   Full Incr Sharpe: {row['full_incr_sharpe']:.3f}")
        print(f"   Val Turnover: {row['val_turnover']:.1%}")
    
    print()
    print("=" * 80)
    
    # Save summary
    summary = {
        'timestamp': timestamp,
        'total_configs': len(df),
        'best_config': {
            'budget': float(top5.iloc[0]['budget']),
            'horizon': int(top5.iloc[0]['horizon']),
            'transaction_cost': float(top5.iloc[0]['transaction_cost']),
            'val_incr_sharpe': float(top5.iloc[0]['val_incr_sharpe']),
            'test_incr_sharpe': float(top5.iloc[0]['test_incr_sharpe']),
            'full_incr_sharpe': float(top5.iloc[0]['full_incr_sharpe']),
        },
        'top5': top5[['budget', 'horizon', 'transaction_cost', 'val_incr_sharpe', 'test_incr_sharpe', 'full_incr_sharpe']].to_dict('records')
    }
    
    summary_file = f'{OUTPUT_DIR}/grid_search_summary_{timestamp}.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary saved to: {summary_file}")
    print()


if __name__ == '__main__':
    main()
