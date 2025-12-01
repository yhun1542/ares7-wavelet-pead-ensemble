#!/usr/bin/env python3
"""
PEAD v1 Grid Search Optimization (Simplified)
==============================================

Uses existing run_ares8_overlay.py main() function for grid search.

Parameters:
- budget: [0.02, 0.05, 0.10]
- horizon: [5, 10, 15, 20]
- fee_rate: [0.0005, 0.001]

Total: 24 configurations

Usage:
    cd /home/ubuntu/ares7-ensemble
    python3 research/pead/run_pead_grid_search_v2.py
"""

import sys
import os
import pandas as pd
import numpy as np
from itertools import product
from datetime import datetime
import json

# Add to path
sys.path.insert(0, '/home/ubuntu/ares7-ensemble')

# Import main function from run_ares8_overlay
from research.pead.run_ares8_overlay import main as run_overlay

# Output directory
OUTPUT_DIR = '/home/ubuntu/ares7-ensemble/results/pead_grid_search'
os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_single_config(budget, horizon, fee_rate, config_num, total_configs):
    """Run single configuration"""
    print(f"\n{'='*80}")
    print(f"[{config_num}/{total_configs}] Config: budget={budget:.1%}, horizon={horizon}d, fee={fee_rate:.2%}")
    print(f"{'='*80}\n")
    
    try:
        # Run overlay
        stats_df = run_overlay(
            horizon=horizon,
            budget=budget,
            fee_rate=fee_rate,
            mode="strength",
        )
        
        # Extract metrics
        result = {
            'config_num': config_num,
            'budget': budget,
            'horizon': horizon,
            'fee_rate': fee_rate,
        }
        
        # Parse stats_df
        for _, row in stats_df.iterrows():
            name = row['name']
            split = row['split']
            
            prefix = f"{name}_{split}"
            result[f"{prefix}_sharpe"] = row['sharpe']
            result[f"{prefix}_ann_return"] = row['ann_return']
            result[f"{prefix}_ann_vol"] = row['ann_vol']
            result[f"{prefix}_mdd"] = row['mdd']
        
        # Calculate incremental Sharpe for each split
        for split in ['all', 'train', 'val', 'test']:
            base_sharpe = result.get(f"base_{split}_sharpe", np.nan)
            overlay_sharpe = result.get(f"overlay_{split}_sharpe", np.nan)
            result[f"incr_sharpe_{split}"] = overlay_sharpe - base_sharpe
        
        # Print summary
        print("\n" + "="*80)
        print("RESULTS SUMMARY")
        print("="*80)
        print(f"Train Incremental Sharpe: {result.get('incr_sharpe_train', np.nan):.3f}")
        print(f"Val Incremental Sharpe:   {result.get('incr_sharpe_val', np.nan):.3f}")
        print(f"Test Incremental Sharpe:  {result.get('incr_sharpe_test', np.nan):.3f}")
        print(f"Full Incremental Sharpe:  {result.get('incr_sharpe_all', np.nan):.3f}")
        print("="*80 + "\n")
        
        return result
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        
        return {
            'config_num': config_num,
            'budget': budget,
            'horizon': horizon,
            'fee_rate': fee_rate,
            'error': str(e),
        }


def main():
    """Main grid search"""
    print("=" * 80)
    print("PEAD v1 Grid Search Optimization")
    print("=" * 80)
    print()
    
    # Grid parameters
    budgets = [0.02, 0.05, 0.10]
    horizons = [5, 10, 15, 20]
    fee_rates = [0.0005, 0.001]
    
    configs = list(product(budgets, horizons, fee_rates))
    total_configs = len(configs)
    
    print(f"Grid Search Space:")
    print(f"  Budgets: {[f'{b:.1%}' for b in budgets]}")
    print(f"  Horizons: {horizons}")
    print(f"  Fee Rates: {[f'{f:.2%}' for f in fee_rates]}")
    print(f"  Total Configurations: {total_configs}")
    print()
    
    # Run grid search
    results = []
    
    for i, (budget, horizon, fee_rate) in enumerate(configs, 1):
        result = run_single_config(budget, horizon, fee_rate, i, total_configs)
        results.append(result)
        
        # Save intermediate results
        df = pd.DataFrame(results)
        df.to_csv(f'{OUTPUT_DIR}/grid_search_results_temp.csv', index=False)
        print(f"✅ Intermediate results saved ({i}/{total_configs})\n")
    
    # Final results
    df = pd.DataFrame(results)
    
    # Sort by validation incremental Sharpe
    df = df.sort_values('incr_sharpe_val', ascending=False)
    
    # Save
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f'{OUTPUT_DIR}/grid_search_results_{timestamp}.csv'
    df.to_csv(output_file, index=False)
    
    # Summary
    print("\n" + "=" * 80)
    print("GRID SEARCH COMPLETE")
    print("=" * 80)
    print(f"\nResults saved to: {output_file}\n")
    
    # Top 5
    print("Top 5 Configurations (by Validation Incremental Sharpe):")
    print("-" * 80)
    
    top5 = df.head(5)
    for idx, row in top5.iterrows():
        print(f"\n{idx+1}. Budget={row['budget']:.1%}, Horizon={row['horizon']:.0f}d, Fee={row['fee_rate']:.2%}")
        print(f"   Val Incr Sharpe:  {row.get('incr_sharpe_val', np.nan):.3f}")
        print(f"   Test Incr Sharpe: {row.get('incr_sharpe_test', np.nan):.3f}")
        print(f"   Full Incr Sharpe: {row.get('incr_sharpe_all', np.nan):.3f}")
    
    print("\n" + "=" * 80 + "\n")
    
    # Save summary JSON
    summary = {
        'timestamp': timestamp,
        'total_configs': total_configs,
        'best_config': {
            'budget': float(top5.iloc[0]['budget']),
            'horizon': int(top5.iloc[0]['horizon']),
            'fee_rate': float(top5.iloc[0]['fee_rate']),
            'val_incr_sharpe': float(top5.iloc[0].get('incr_sharpe_val', np.nan)),
            'test_incr_sharpe': float(top5.iloc[0].get('incr_sharpe_test', np.nan)),
            'full_incr_sharpe': float(top5.iloc[0].get('incr_sharpe_all', np.nan)),
        }
    }
    
    summary_file = f'{OUTPUT_DIR}/grid_search_summary_{timestamp}.json'
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary saved to: {summary_file}\n")


if __name__ == '__main__':
    main()
