#!/usr/bin/env python3
"""
PEAD + Buyback Ensemble Overlay
AI Model 2 방식: 이벤트 테이블 병합 → Pure Tilt
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd
import numpy as np
from research.pead.event_book import EventBook
# Period splits
TRAIN_START, TRAIN_END = '2015-01-01', '2018-12-31'
VAL_START, VAL_END = '2019-01-01', '2021-12-31'
TEST_START, TEST_END = '2022-01-01', '2025-11-18'

# ============================================================================
# Configuration
# ============================================================================

PEAD_WEIGHT = 0.6
BUYBACK_WEIGHT = 0.4
TILT_SIZE = 0.015  # 1.5%p (optimized)
HORIZON = 30  # days (optimized)
MIN_RANK = 0.0  # No filtering (already top 10%)

# ============================================================================
# Load Data
# ============================================================================

print("Loading data...")

# Prices
px_long = pd.read_csv(project_root / "data" / "prices.csv")
px_long['timestamp'] = pd.to_datetime(px_long['timestamp']).dt.normalize()
px = px_long.pivot(index='timestamp', columns='symbol', values='close')
px = px.ffill()  # Forward fill

# Base weights (vol-weighted)
base_long = pd.read_csv(project_root / "data" / "ares7_base_weights.csv")
base_long['date'] = pd.to_datetime(base_long['date']).dt.normalize()
base = base_long.pivot(index='date', columns='symbol', values='weight')
base = base.reindex(px.index).ffill()

# PEAD events
pead_events = pd.read_csv(project_root / "data" / "pead_event_table_positive.csv")
pead_events['date'] = pd.to_datetime(pead_events['date']).dt.normalize()
pead_events = pead_events.rename(columns={'symbol': 'ticker'})
pead_events['bucket'] = 'pos_top'  # All positive surprise
pead_events['signal_rank'] = pead_events['surprise_rank']

# Buyback events
buyback_events = pd.read_csv(project_root / "data" / "buyback_events.csv")
buyback_events['event_date'] = pd.to_datetime(buyback_events['event_date']).dt.normalize()
buyback_events = buyback_events.rename(columns={'event_date': 'date'})
# Already has bucket='bb_top' and signal_rank

print(f"PEAD events: {len(pead_events)}")
print(f"Buyback events: {len(buyback_events)}")

# ============================================================================
# Ensemble: Merge Events
# ============================================================================

print("\nMerging events...")

# Add source column
pead_events['source'] = 'pead'
buyback_events['source'] = 'buyback'

# Select common columns
common_cols = ['date', 'ticker', 'bucket', 'signal_rank', 'source']

pead_subset = pead_events[common_cols].copy()
buyback_subset = buyback_events[common_cols].copy()

# Merge
ensemble_events = pd.concat([pead_subset, buyback_subset], ignore_index=True)

# Adjust signal_rank by weight
ensemble_events['weighted_rank'] = ensemble_events.apply(
    lambda row: row['signal_rank'] * PEAD_WEIGHT if row['source'] == 'pead' 
                else row['signal_rank'] * BUYBACK_WEIGHT,
    axis=1
)

# Sort by date and weighted_rank
ensemble_events = ensemble_events.sort_values(['date', 'weighted_rank'], ascending=[True, False])

print(f"Ensemble events: {len(ensemble_events)}")
print(f"  PEAD: {len(ensemble_events[ensemble_events['source']=='pead'])}")
print(f"  Buyback: {len(ensemble_events[ensemble_events['source']=='buyback'])}")

# ============================================================================
# Pure Tilt Backtest
# ============================================================================

print("\nRunning Pure Tilt backtest...")

# Initialize event book
event_book = EventBook()

# Returns
px_ret = px.pct_change()

# Overlay weights (start with base)
overlay_wt = base.copy()

# Track statistics
stats_by_period = {'train': [], 'val': [], 'test': []}

for t in px.index[1:]:
    # Check for new events
    events_today = ensemble_events[ensemble_events['date'] == t]
    
    for _, event in events_today.iterrows():
        ticker = event['ticker']
        if ticker not in px.columns:
            continue
        
        if event['weighted_rank'] < MIN_RANK:
            continue
        
        # Add event to book
        event_book.add_event(
            symbol=ticker,
            open_date=t,
            horizon_days=HORIZON,
            tilt_amount=TILT_SIZE
        )
    
    # Get current tilts
    tilts = event_book.get_active_tilts(t)
    
    # Apply tilts to base weights
    if t in base.index:
        base_wt = base.loc[t]
        
        # Start with base
        new_wt = base_wt.copy()
        
        # Apply tilts
        for ticker, tilt in tilts.items():
            if ticker in new_wt.index:
                new_wt[ticker] += tilt
        
        # Normalize
        new_wt = new_wt.clip(lower=0)
        if new_wt.sum() > 0:
            new_wt /= new_wt.sum()
        
        overlay_wt.loc[t] = new_wt
    
    # Close expired events
    event_book.close_expired_events(t)

# ============================================================================
# Compute Performance
# ============================================================================

print("\nComputing performance...")

# Portfolio returns
base_ret = (base.shift(1) * px_ret).sum(axis=1)
overlay_ret = (overlay_wt.shift(1) * px_ret).sum(axis=1)
incr_ret = overlay_ret - base_ret

# Split by period
def get_period_stats(returns, name):
    if name == 'train':
        r = returns[TRAIN_START:TRAIN_END]
    elif name == 'val':
        r = returns[VAL_START:VAL_END]
    else:  # test
        r = returns[TEST_START:TEST_END]
    
    r = r.dropna()
    if len(r) == 0:
        return {'sharpe': 0, 'ret': 0, 'vol': 0}
    
    sharpe = r.mean() / r.std() * np.sqrt(252) if r.std() > 0 else 0
    ret = r.mean() * 252
    vol = r.std() * np.sqrt(252)
    
    return {'sharpe': sharpe, 'ret': ret, 'vol': vol}

# Compute stats
periods = ['train', 'val', 'test', 'full']
results = {}

for period in periods:
    if period == 'full':
        r_base = base_ret
        r_overlay = overlay_ret
        r_incr = incr_ret
    else:
        if period == 'train':
            r_base = base_ret[TRAIN_START:TRAIN_END]
            r_overlay = overlay_ret[TRAIN_START:TRAIN_END]
            r_incr = incr_ret[TRAIN_START:TRAIN_END]
        elif period == 'val':
            r_base = base_ret[VAL_START:VAL_END]
            r_overlay = overlay_ret[VAL_START:VAL_END]
            r_incr = incr_ret[VAL_START:VAL_END]
        else:  # test
            r_base = base_ret[TEST_START:TEST_END]
            r_overlay = overlay_ret[TEST_START:TEST_END]
            r_incr = incr_ret[TEST_START:TEST_END]
    
    r_base = r_base.dropna()
    r_overlay = r_overlay.dropna()
    r_incr = r_incr.dropna()
    
    results[period] = {
        'base_sharpe': r_base.mean() / r_base.std() * np.sqrt(252) if r_base.std() > 0 else 0,
        'overlay_sharpe': r_overlay.mean() / r_overlay.std() * np.sqrt(252) if r_overlay.std() > 0 else 0,
        'incr_sharpe': r_incr.mean() / r_incr.std() * np.sqrt(252) if r_incr.std() > 0 else 0,
        'incr_ret': r_incr.mean() * 252,
        'incr_vol': r_incr.std() * np.sqrt(252)
    }

# ============================================================================
# Print Results
# ============================================================================

print("\n" + "="*80)
print("PEAD + Buyback Ensemble Results")
print("="*80)

print(f"\nEnsemble Configuration:")
print(f"  PEAD Weight: {PEAD_WEIGHT*100:.0f}%")
print(f"  Buyback Weight: {BUYBACK_WEIGHT*100:.0f}%")
print(f"  Tilt Size: {TILT_SIZE*100:.2f}%p")
print(f"  Horizon: {HORIZON} days")

print(f"\nEvent Statistics:")
print(f"  Total events: {len(ensemble_events)}")
print(f"  PEAD: {len(ensemble_events[ensemble_events['source']=='pead'])} ({len(ensemble_events[ensemble_events['source']=='pead'])/len(ensemble_events)*100:.1f}%)")
print(f"  Buyback: {len(ensemble_events[ensemble_events['source']=='buyback'])} ({len(ensemble_events[ensemble_events['source']=='buyback'])/len(ensemble_events)*100:.1f}%)")

print(f"\nEvent Book History:")
history = event_book.event_history
print(f"  Events opened: {len(history)}")
print(f"  Events closed: {len([e for e in history if e['close_date'] is not None])}")

print(f"\nPerformance by Period:")
print(f"{'Period':<10} {'Base Sharpe':>12} {'Overlay Sharpe':>15} {'Incr Sharpe':>13} {'Incr Ret':>10} {'Incr Vol':>10}")
print("-"*80)

for period in ['train', 'val', 'test', 'full']:
    r = results[period]
    print(f"{period.capitalize():<10} {r['base_sharpe']:>12.3f} {r['overlay_sharpe']:>15.3f} {r['incr_sharpe']:>13.3f} {r['incr_ret']:>9.2%} {r['incr_vol']:>9.2%}")

print("\n" + "="*80)
print(f"✅ Combined Sharpe: {results['full']['overlay_sharpe']:.3f}")
print(f"{'✅' if results['full']['overlay_sharpe'] > 1.0 else '⚠️'} Target (>1.0): {'ACHIEVED' if results['full']['overlay_sharpe'] > 1.0 else 'NOT ACHIEVED'}")
print("="*80)

# Save results
output_dir = project_root / "results" / "ensemble"
output_dir.mkdir(parents=True, exist_ok=True)

summary = pd.DataFrame(results).T
summary.to_csv(output_dir / "ensemble_pead_buyback_summary.csv")

print(f"\n✅ Results saved to {output_dir}")
