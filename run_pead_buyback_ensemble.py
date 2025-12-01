#!/usr/bin/env python3.11
"""
run_pead_buyback_ensemble.py

용도:
  - ARES7 Base + PEAD + Buyback 세 가지를 동시에 비교하는 "분석용" 스크립트.
    - base: ares7_base_weights.csv 기반 포트폴리오 PnL
    - pead: pead_event_table_positive.csv 기반 이벤트 롱 포트폴리오 (상위 quantile)
    - buyback: buyback_events.csv에서 bucket=='bb_top'인 이벤트 포트폴리오
    - ensemble: base + α_pead * pead + α_bb * buyback

중요한 제약:
  - PRODUCTION: alpha_bb = 0.0 으로 고정 (즉, ensemble == base + α_pead * pead).
  - R&D: alpha_bb > 0는 오직 R&D/실험 모드에서만 수동으로 허용.

출력:
  - strategy × split별 Sharpe, IR, max drawdown 등의 테이블.

Author: ARES7/ARES8 Research Team
Date: 2025-12-01
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Tuple

# Project root
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from research.pead.event_book import EventBook

# ============================================================================
# Configuration
# ============================================================================

# Paths
DATA_DIR = project_root / "data"
PRICES_PATH = DATA_DIR / "prices.csv"
BASE_WEIGHTS_PATH = DATA_DIR / "ares7_base_weights.csv"
PEAD_EVENTS_PATH = DATA_DIR / "pead_event_table_positive.csv"
BUYBACK_EVENTS_PATH = DATA_DIR / "buyback_events.csv"

# Output
OUTPUT_DIR = project_root / "ensemble_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Period splits (aligned with PEAD research)
TRAIN_START, TRAIN_END = '2016-01-01', '2018-12-31'
VAL_START, VAL_END = '2019-01-01', '2021-12-31'
TEST_START, TEST_END = '2022-01-01', '2025-11-18'

# ============================================================================
# PRODUCTION: PEAD Only (Buyback weight = 0)
# ============================================================================
ALPHA_PEAD = 1.0      # PEAD overlay weight
ALPHA_BB = 0.0        # PRODUCTION: Buyback overlay OFF

# ============================================================================
# R&D: Experimental mode (uncomment to test Buyback)
# ============================================================================
# ALPHA_PEAD = 0.6
# ALPHA_BB = 0.4

# ============================================================================
# Pure Tilt Parameters (optimized from PEAD research)
# ============================================================================
TILT_SIZE = 0.015     # 1.5%p
HORIZON = 30          # days
MIN_RANK = 0.0        # No filtering (already top 10%)

# ============================================================================
# Data Loading
# ============================================================================

def load_prices() -> pd.DataFrame:
    """Load price matrix"""
    print("Loading prices...")
    px_long = pd.read_csv(PRICES_PATH)
    px_long['timestamp'] = pd.to_datetime(px_long['timestamp']).dt.normalize()
    px = px_long.pivot(index='timestamp', columns='symbol', values='close')
    px = px.ffill()
    print(f"  Shape: {px.shape}")
    print(f"  Date range: {px.index.min()} to {px.index.max()}")
    return px


def load_base_weights(px: pd.DataFrame) -> pd.DataFrame:
    """Load ARES7 base portfolio weights (vol-weighted)"""
    print("Loading base weights...")
    base_long = pd.read_csv(BASE_WEIGHTS_PATH)
    base_long['date'] = pd.to_datetime(base_long['date']).dt.normalize()
    base = base_long.pivot(index='date', columns='symbol', values='weight')
    base = base.reindex(px.index).ffill()
    print(f"  Shape: {base.shape}")
    return base


def load_pead_events() -> pd.DataFrame:
    """Load PEAD events (positive surprise only)"""
    print("Loading PEAD events...")
    pead = pd.read_csv(PEAD_EVENTS_PATH)
    pead['date'] = pd.to_datetime(pead['date']).dt.normalize()
    pead = pead.rename(columns={'symbol': 'ticker'})
    pead['bucket'] = 'pos_top'
    pead['signal_rank'] = pead['surprise_rank']
    pead['weighted_rank'] = pead['signal_rank']  # Will be adjusted in ensemble
    pead['source'] = 'pead'
    print(f"  Events: {len(pead)}")
    return pead


def load_buyback_events(px: pd.DataFrame) -> pd.DataFrame:
    """Load Buyback events (filtered to price universe)"""
    print("Loading buyback events...")
    bb = pd.read_csv(BUYBACK_EVENTS_PATH)
    bb['event_date'] = pd.to_datetime(bb['event_date']).dt.normalize()
    bb = bb.rename(columns={'event_date': 'date'})
    
    # Filter to price universe
    valid_dates = set(px.index)
    valid_symbols = set(px.columns)
    before_n = len(bb)
    bb = bb[bb['date'].isin(valid_dates)]
    bb = bb[bb['ticker'].isin(valid_symbols)]
    after_n = len(bb)
    
    bb['weighted_rank'] = bb['signal_rank']  # Will be adjusted in ensemble
    bb['source'] = 'buyback'
    print(f"  Events: {after_n} (filtered from {before_n})")
    return bb


# ============================================================================
# Portfolio Construction
# ============================================================================

def build_ensemble_events(
    pead_events: pd.DataFrame,
    buyback_events: pd.DataFrame,
    alpha_pead: float,
    alpha_bb: float
) -> pd.DataFrame:
    """
    Merge PEAD and Buyback events with weighted signal ranks.
    
    PRODUCTION: alpha_bb = 0.0 → only PEAD events used
    R&D: alpha_bb > 0 → both PEAD and Buyback events used
    """
    print(f"\nBuilding ensemble events (α_pead={alpha_pead}, α_bb={alpha_bb})...")
    
    # Select common columns
    common_cols = ['date', 'ticker', 'bucket', 'signal_rank', 'source']
    
    pead_subset = pead_events[common_cols].copy()
    buyback_subset = buyback_events[common_cols].copy()
    
    # Merge
    if alpha_bb == 0.0:
        # PRODUCTION: PEAD Only
        ensemble = pead_subset.copy()
        print("  Mode: PRODUCTION (PEAD Only)")
    else:
        # R&D: PEAD + Buyback
        ensemble = pd.concat([pead_subset, buyback_subset], ignore_index=True)
        print("  Mode: R&D (PEAD + Buyback)")
    
    # Adjust signal_rank by weight
    ensemble['weighted_rank'] = ensemble.apply(
        lambda row: row['signal_rank'] * alpha_pead if row['source'] == 'pead' 
                    else row['signal_rank'] * alpha_bb,
        axis=1
    )
    
    # Sort by date and weighted_rank
    ensemble = ensemble.sort_values(['date', 'weighted_rank'], ascending=[True, False])
    
    print(f"  Total events: {len(ensemble)}")
    print(f"    PEAD: {len(ensemble[ensemble['source']=='pead'])}")
    print(f"    Buyback: {len(ensemble[ensemble['source']=='buyback'])}")
    
    return ensemble


def run_pure_tilt_backtest(
    events: pd.DataFrame,
    base_weights: pd.DataFrame,
    px: pd.DataFrame,
    tilt_size: float,
    horizon: int,
    min_rank: float
) -> Tuple[pd.Series, pd.DataFrame]:
    """
    Run Pure Tilt overlay backtest.
    
    Returns:
        - portfolio_ret: Daily portfolio returns
        - overlay_weights: Daily overlay weights (date × symbol)
    """
    print(f"\nRunning Pure Tilt backtest (tilt={tilt_size}, horizon={horizon})...")
    
    # Initialize event book
    event_book = EventBook()
    
    # Returns
    px_ret = px.pct_change()
    
    # Overlay weights (start with base)
    overlay_wt = base_weights.copy()
    
    # Track daily portfolio returns
    portfolio_ret = []
    
    for t in px.index[1:]:
        # Check for new events
        events_today = events[events['date'] == t]
        
        for _, event in events_today.iterrows():
            ticker = event['ticker']
            if ticker not in px.columns:
                continue
            
            if event['weighted_rank'] < min_rank:
                continue
            
            # Add event to book
            event_book.add_event(
                symbol=ticker,
                open_date=t,
                horizon_days=horizon,
                tilt_amount=tilt_size
            )
        
        # Get current tilts
        tilts = event_book.get_active_tilts(t)
        
        # Apply tilts to base weights
        if t in base_weights.index:
            base_wt = base_weights.loc[t]
            
            # Start with base
            new_wt = base_wt.copy()
            
            # Apply tilts
            for ticker, tilt in tilts.items():
                if ticker in new_wt.index:
                    new_wt[ticker] += tilt
            
            # Normalize to sum to 1
            new_wt = new_wt / new_wt.sum()
            
            # Store overlay weights
            overlay_wt.loc[t] = new_wt
            
            # Compute portfolio return
            if t in px_ret.index:
                ret_today = (new_wt * px_ret.loc[t]).sum()
                portfolio_ret.append({'date': t, 'ret': ret_today})
    
    # Convert to Series
    portfolio_ret = pd.DataFrame(portfolio_ret).set_index('date')['ret']
    
    print(f"  Backtest days: {len(portfolio_ret)}")
    
    return portfolio_ret, overlay_wt


def compute_base_returns(
    base_weights: pd.DataFrame,
    px: pd.DataFrame
) -> pd.Series:
    """Compute base portfolio returns (no overlay)"""
    print("\nComputing base portfolio returns...")
    px_ret = px.pct_change()
    
    base_ret = []
    for t in px.index[1:]:
        if t in base_weights.index and t in px_ret.index:
            wt = base_weights.loc[t]
            ret = (wt * px_ret.loc[t]).sum()
            base_ret.append({'date': t, 'ret': ret})
    
    base_ret = pd.DataFrame(base_ret).set_index('date')['ret']
    print(f"  Base return days: {len(base_ret)}")
    return base_ret


# ============================================================================
# Performance Metrics
# ============================================================================

def compute_metrics(
    returns: pd.Series,
    split_name: str,
    start_date: str,
    end_date: str
) -> Dict:
    """Compute performance metrics for a given period"""
    ret_period = returns[(returns.index >= start_date) & (returns.index <= end_date)]
    
    if len(ret_period) < 20:
        return {
            'split': split_name,
            'n_days': len(ret_period),
            'total_ret': np.nan,
            'ann_ret': np.nan,
            'ann_vol': np.nan,
            'sharpe': np.nan,
            'max_dd': np.nan,
        }
    
    total_ret = (1 + ret_period).prod() - 1
    ann_ret = (1 + total_ret) ** (252 / len(ret_period)) - 1
    ann_vol = ret_period.std() * np.sqrt(252)
    sharpe = ann_ret / (ann_vol + 1e-9)
    
    # Max drawdown
    cum_ret = (1 + ret_period).cumprod()
    running_max = cum_ret.expanding().max()
    drawdown = (cum_ret - running_max) / running_max
    max_dd = drawdown.min()
    
    return {
        'split': split_name,
        'n_days': len(ret_period),
        'total_ret': total_ret,
        'ann_ret': ann_ret,
        'ann_vol': ann_vol,
        'sharpe': sharpe,
        'max_dd': max_dd,
    }


def summarize_performance(
    base_ret: pd.Series,
    pead_ret: pd.Series,
    buyback_ret: pd.Series,
    ensemble_ret: pd.Series
) -> pd.DataFrame:
    """Summarize performance across all strategies and splits"""
    print("\nSummarizing performance...")
    
    strategies = {
        'base': base_ret,
        'pead': pead_ret,
        'buyback': buyback_ret,
        'ensemble': ensemble_ret,
    }
    
    splits = [
        ('train', TRAIN_START, TRAIN_END),
        ('val', VAL_START, VAL_END),
        ('test', TEST_START, TEST_END),
    ]
    
    results = []
    for strat_name, strat_ret in strategies.items():
        for split_name, start, end in splits:
            metrics = compute_metrics(strat_ret, split_name, start, end)
            metrics['strategy'] = strat_name
            results.append(metrics)
    
    df = pd.DataFrame(results)
    df = df[['strategy', 'split', 'n_days', 'total_ret', 'ann_ret', 'ann_vol', 'sharpe', 'max_dd']]
    
    return df


# ============================================================================
# Main
# ============================================================================

def main():
    print("=" * 80)
    print("PEAD + BUYBACK ENSEMBLE ANALYSIS")
    print("=" * 80)
    print(f"PRODUCTION MODE: α_pead={ALPHA_PEAD}, α_bb={ALPHA_BB}")
    if ALPHA_BB > 0:
        print("WARNING: Buyback overlay is ENABLED (R&D mode)")
    else:
        print("INFO: Buyback overlay is DISABLED (PEAD Only)")
    print("=" * 80)
    
    # 1) Load data
    px = load_prices()
    base_weights = load_base_weights(px)
    pead_events = load_pead_events()
    buyback_events = load_buyback_events(px)
    
    # 2) Build ensemble events
    ensemble_events = build_ensemble_events(
        pead_events=pead_events,
        buyback_events=buyback_events,
        alpha_pead=ALPHA_PEAD,
        alpha_bb=ALPHA_BB
    )
    
    # 3) Run backtests
    
    # Base portfolio (no overlay)
    base_ret = compute_base_returns(base_weights, px)
    
    # PEAD Only
    pead_ret, _ = run_pure_tilt_backtest(
        events=pead_events,
        base_weights=base_weights,
        px=px,
        tilt_size=TILT_SIZE,
        horizon=HORIZON,
        min_rank=MIN_RANK
    )
    
    # Buyback Only
    buyback_ret, _ = run_pure_tilt_backtest(
        events=buyback_events,
        base_weights=base_weights,
        px=px,
        tilt_size=TILT_SIZE,
        horizon=HORIZON,
        min_rank=MIN_RANK
    )
    
    # Ensemble (PEAD + Buyback with weights)
    ensemble_ret, _ = run_pure_tilt_backtest(
        events=ensemble_events,
        base_weights=base_weights,
        px=px,
        tilt_size=TILT_SIZE,
        horizon=HORIZON,
        min_rank=MIN_RANK
    )
    
    # 4) Summarize performance
    summary = summarize_performance(
        base_ret=base_ret,
        pead_ret=pead_ret,
        buyback_ret=buyback_ret,
        ensemble_ret=ensemble_ret
    )
    
    # 5) Display results
    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)
    print(summary.to_string(index=False))
    
    # 6) Save to CSV
    summary_path = OUTPUT_DIR / "ensemble_summary.csv"
    summary.to_csv(summary_path, index=False)
    
    print(f"\n[INFO] Results saved to: {summary_path}")
    
    # 7) Key insights
    print("\n" + "=" * 80)
    print("KEY INSIGHTS")
    print("=" * 80)
    
    # Compare PEAD vs Ensemble in Test
    pead_test = summary[(summary['strategy'] == 'pead') & (summary['split'] == 'test')]['sharpe'].values[0]
    ensemble_test = summary[(summary['strategy'] == 'ensemble') & (summary['split'] == 'test')]['sharpe'].values[0]
    
    print(f"PEAD Test Sharpe: {pead_test:.3f}")
    print(f"Ensemble Test Sharpe: {ensemble_test:.3f}")
    
    if ALPHA_BB == 0.0:
        print("\nPRODUCTION: PEAD Only (Buyback weight = 0)")
        print("  → Ensemble == PEAD (as expected)")
    else:
        delta = ensemble_test - pead_test
        print(f"\nR&D: PEAD + Buyback (α_bb={ALPHA_BB})")
        print(f"  → Ensemble vs PEAD: {delta:+.3f} Sharpe")
        if delta < 0:
            print("  → WARNING: Buyback degrades performance")
    
    print("\n" + "=" * 80)
    print("ENSEMBLE ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
