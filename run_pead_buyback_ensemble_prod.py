#!/usr/bin/env python3.11
"""
run_pead_buyback_ensemble_prod.py

================================================================================
PRODUCTION VERSION - PEAD Only Overlay (Buyback Disabled)
================================================================================

용도:
  - ARES7 Base + PEAD Overlay 전략을 프로덕션 환경에서 실행
  - Buyback은 **완전히 비활성화** (α_bb = 0.0 강제)
  
안전장치:
  - MODE 환경변수로 실행 모드 제어 (PROD/RD)
  - PROD 모드에서는 α_bb를 0.0으로 강제 (코드 레벨 방어)
  - R&D 모드는 환경변수 ENABLE_RD_MODE=1 설정 시에만 활성화
  
실행 방법:
  - PRODUCTION: python3.11 run_pead_buyback_ensemble_prod.py
  - R&D: ENABLE_RD_MODE=1 python3.11 run_pead_buyback_ensemble_prod.py

Author: ARES7/ARES8 Research Team
Date: 2025-12-01
Version: PRODUCTION v1.0
================================================================================
"""

import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, Tuple
from datetime import datetime

# Project root
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from research.pead.event_book import EventBook

# ============================================================================
# PRODUCTION MODE ENFORCEMENT
# ============================================================================

# 환경변수로 모드 결정
ENABLE_RD_MODE = os.getenv("ENABLE_RD_MODE", "0") == "1"

if ENABLE_RD_MODE:
    MODE = "RD"
    print("=" * 80)
    print("⚠️  WARNING: R&D MODE ENABLED")
    print("=" * 80)
    print("This mode allows Buyback overlay for research purposes.")
    print("DO NOT use this mode in production deployment!")
    print("=" * 80)
else:
    MODE = "PROD"
    print("=" * 80)
    print("✅ PRODUCTION MODE")
    print("=" * 80)
    print("PEAD Only Overlay (Buyback Disabled)")
    print("=" * 80)

# ============================================================================
# ALPHA WEIGHTS - PRODUCTION ENFORCEMENT
# ============================================================================

# PRODUCTION: PEAD Only (Buyback weight = 0)
ALPHA_PEAD_PROD = 1.0
ALPHA_BB_PROD = 0.0

# R&D: Experimental weights (only if ENABLE_RD_MODE=1)
ALPHA_PEAD_RD = 0.6
ALPHA_BB_RD = 0.4

# 모드에 따라 가중치 결정
if MODE == "PROD":
    ALPHA_PEAD = ALPHA_PEAD_PROD
    ALPHA_BB = ALPHA_BB_PROD
    
    # PRODUCTION 모드에서는 α_bb를 강제로 0.0으로 고정
    # 코드 레벨 방어: 어떤 경우에도 변경 불가
    ALPHA_BB = 0.0  # CRITICAL: DO NOT MODIFY IN PRODUCTION
    
    print(f"Alpha PEAD: {ALPHA_PEAD}")
    print(f"Alpha Buyback: {ALPHA_BB} (LOCKED)")
else:
    ALPHA_PEAD = ALPHA_PEAD_RD
    ALPHA_BB = ALPHA_BB_RD
    
    print(f"Alpha PEAD: {ALPHA_PEAD}")
    print(f"Alpha Buyback: {ALPHA_BB} (R&D Mode)")

print("=" * 80)

# ============================================================================
# Paths
# ============================================================================

DATA_DIR = project_root / "data"
PRICES_PATH = DATA_DIR / "prices.csv"
BASE_WEIGHTS_PATH = DATA_DIR / "ares7_base_weights.csv"
PEAD_EVENTS_PATH = DATA_DIR / "pead_event_table_positive.csv"
BUYBACK_EVENTS_PATH = DATA_DIR / "buyback_events.csv"

# Output
OUTPUT_DIR = project_root / "ensemble_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

# Logging
LOG_DIR = project_root / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / f"ensemble_{MODE.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# ============================================================================
# Period splits
# ============================================================================

TRAIN_START, TRAIN_END = '2016-01-01', '2018-12-31'
VAL_START, VAL_END = '2019-01-01', '2021-12-31'
TEST_START, TEST_END = '2022-01-01', '2025-11-18'

# ============================================================================
# Pure Tilt Parameters (optimized from PEAD research)
# ============================================================================

TILT_SIZE = 0.015     # 1.5%p
HORIZON = 30          # days
MIN_RANK = 0.0        # No filtering (already top 10%)

# ============================================================================
# Logging Setup
# ============================================================================

def log_message(msg: str, to_file: bool = True, to_console: bool = True):
    """Log message to file and/or console"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {msg}"
    
    if to_console:
        print(log_line)
    
    if to_file:
        with open(LOG_FILE, 'a') as f:
            f.write(log_line + '\n')

# ============================================================================
# Data Loading
# ============================================================================

def load_prices() -> pd.DataFrame:
    """Load price matrix"""
    log_message("Loading prices...")
    px_long = pd.read_csv(PRICES_PATH)
    px_long['timestamp'] = pd.to_datetime(px_long['timestamp']).dt.normalize()
    px = px_long.pivot(index='timestamp', columns='symbol', values='close')
    px = px.ffill()
    log_message(f"  Shape: {px.shape}")
    log_message(f"  Date range: {px.index.min()} to {px.index.max()}")
    return px


def load_base_weights(px: pd.DataFrame) -> pd.DataFrame:
    """Load ARES7 base portfolio weights (vol-weighted)"""
    log_message("Loading base weights...")
    base_long = pd.read_csv(BASE_WEIGHTS_PATH)
    base_long['date'] = pd.to_datetime(base_long['date']).dt.normalize()
    base = base_long.pivot(index='date', columns='symbol', values='weight')
    base = base.reindex(px.index).ffill()
    log_message(f"  Shape: {base.shape}")
    return base


def load_pead_events() -> pd.DataFrame:
    """Load PEAD events (positive surprise only)"""
    log_message("Loading PEAD events...")
    pead = pd.read_csv(PEAD_EVENTS_PATH)
    pead['date'] = pd.to_datetime(pead['date']).dt.normalize()
    pead = pead.rename(columns={'symbol': 'ticker'})
    pead['bucket'] = 'pos_top'
    pead['signal_rank'] = pead['surprise_rank']
    pead['weighted_rank'] = pead['signal_rank']
    pead['source'] = 'pead'
    log_message(f"  Events: {len(pead)}")
    return pead


def load_buyback_events(px: pd.DataFrame) -> pd.DataFrame:
    """Load Buyback events (filtered to price universe)"""
    log_message("Loading buyback events...")
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
    
    bb['weighted_rank'] = bb['signal_rank']
    bb['source'] = 'buyback'
    log_message(f"  Events: {after_n} (filtered from {before_n})")
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
    log_message(f"\nBuilding ensemble events (α_pead={alpha_pead}, α_bb={alpha_bb})...")
    
    # Select common columns
    common_cols = ['date', 'ticker', 'bucket', 'signal_rank', 'source']
    
    pead_subset = pead_events[common_cols].copy()
    buyback_subset = buyback_events[common_cols].copy()
    
    # PRODUCTION MODE: Buyback 완전 제외
    if alpha_bb == 0.0:
        ensemble = pead_subset.copy()
        log_message("  Mode: PRODUCTION (PEAD Only)")
    else:
        # R&D MODE: PEAD + Buyback
        ensemble = pd.concat([pead_subset, buyback_subset], ignore_index=True)
        log_message("  Mode: R&D (PEAD + Buyback)")
    
    # Adjust signal_rank by weight
    ensemble['weighted_rank'] = ensemble.apply(
        lambda row: row['signal_rank'] * alpha_pead if row['source'] == 'pead' 
                    else row['signal_rank'] * alpha_bb,
        axis=1
    )
    
    # Sort by date and weighted_rank
    ensemble = ensemble.sort_values(['date', 'weighted_rank'], ascending=[True, False])
    
    log_message(f"  Total events: {len(ensemble)}")
    log_message(f"    PEAD: {len(ensemble[ensemble['source']=='pead'])}")
    log_message(f"    Buyback: {len(ensemble[ensemble['source']=='buyback'])}")
    
    return ensemble


def run_pure_tilt_backtest(
    events: pd.DataFrame,
    base_weights: pd.DataFrame,
    px: pd.DataFrame,
    tilt_size: float,
    horizon: int,
    min_rank: float
) -> Tuple[pd.Series, pd.DataFrame]:
    """Run Pure Tilt overlay backtest"""
    log_message(f"\nRunning Pure Tilt backtest (tilt={tilt_size}, horizon={horizon})...")
    
    event_book = EventBook()
    px_ret = px.pct_change()
    overlay_wt = base_weights.copy()
    portfolio_ret = []
    
    for t in px.index[1:]:
        events_today = events[events['date'] == t]
        
        for _, event in events_today.iterrows():
            ticker = event['ticker']
            if ticker not in px.columns:
                continue
            
            if event['weighted_rank'] < min_rank:
                continue
            
            event_book.add_event(
                symbol=ticker,
                open_date=t,
                horizon_days=horizon,
                tilt_amount=tilt_size
            )
        
        tilts = event_book.get_active_tilts(t)
        
        if t in base_weights.index:
            base_wt = base_weights.loc[t]
            new_wt = base_wt.copy()
            
            for ticker, tilt in tilts.items():
                if ticker in new_wt.index:
                    new_wt[ticker] += tilt
            
            new_wt = new_wt / new_wt.sum()
            overlay_wt.loc[t] = new_wt
            
            if t in px_ret.index:
                ret_today = (new_wt * px_ret.loc[t]).sum()
                portfolio_ret.append({'date': t, 'ret': ret_today})
    
    portfolio_ret = pd.DataFrame(portfolio_ret).set_index('date')['ret']
    log_message(f"  Backtest days: {len(portfolio_ret)}")
    
    return portfolio_ret, overlay_wt


def compute_base_returns(
    base_weights: pd.DataFrame,
    px: pd.DataFrame
) -> pd.Series:
    """Compute base portfolio returns (no overlay)"""
    log_message("\nComputing base portfolio returns...")
    px_ret = px.pct_change()
    
    base_ret = []
    for t in px.index[1:]:
        if t in base_weights.index and t in px_ret.index:
            wt = base_weights.loc[t]
            ret = (wt * px_ret.loc[t]).sum()
            base_ret.append({'date': t, 'ret': ret})
    
    base_ret = pd.DataFrame(base_ret).set_index('date')['ret']
    log_message(f"  Base return days: {len(base_ret)}")
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
    overlay_ret: pd.Series
) -> pd.DataFrame:
    """Summarize performance across all strategies and splits"""
    log_message("\nSummarizing performance...")
    
    strategies = {
        'base': base_ret,
        'overlay': overlay_ret,
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
    log_message("=" * 80)
    log_message(f"ARES8 ENSEMBLE - {MODE} MODE")
    log_message("=" * 80)
    log_message(f"Alpha PEAD: {ALPHA_PEAD}")
    log_message(f"Alpha Buyback: {ALPHA_BB}")
    
    if ALPHA_BB > 0:
        log_message("⚠️  WARNING: Buyback overlay is ENABLED (R&D mode)")
    else:
        log_message("✅ Buyback overlay is DISABLED (PRODUCTION mode)")
    
    log_message("=" * 80)
    
    # Load data
    px = load_prices()
    base_weights = load_base_weights(px)
    pead_events = load_pead_events()
    buyback_events = load_buyback_events(px)
    
    # Build ensemble events
    ensemble_events = build_ensemble_events(
        pead_events=pead_events,
        buyback_events=buyback_events,
        alpha_pead=ALPHA_PEAD,
        alpha_bb=ALPHA_BB
    )
    
    # Run backtests
    base_ret = compute_base_returns(base_weights, px)
    
    overlay_ret, _ = run_pure_tilt_backtest(
        events=ensemble_events,
        base_weights=base_weights,
        px=px,
        tilt_size=TILT_SIZE,
        horizon=HORIZON,
        min_rank=MIN_RANK
    )
    
    # Summarize performance
    summary = summarize_performance(
        base_ret=base_ret,
        overlay_ret=overlay_ret
    )
    
    # Display results
    log_message("\n" + "=" * 80)
    log_message("PERFORMANCE SUMMARY")
    log_message("=" * 80)
    log_message("\n" + summary.to_string(index=False))
    
    # Save to CSV
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    summary_path = OUTPUT_DIR / f"ensemble_summary_{MODE.lower()}_{timestamp}.csv"
    summary.to_csv(summary_path, index=False)
    
    log_message(f"\n[INFO] Results saved to: {summary_path}")
    
    # Key insights
    log_message("\n" + "=" * 80)
    log_message("KEY INSIGHTS")
    log_message("=" * 80)
    
    base_test = summary[(summary['strategy'] == 'base') & (summary['split'] == 'test')]['sharpe'].values[0]
    overlay_test = summary[(summary['strategy'] == 'overlay') & (summary['split'] == 'test')]['sharpe'].values[0]
    
    log_message(f"Base Test Sharpe: {base_test:.3f}")
    log_message(f"Overlay Test Sharpe: {overlay_test:.3f}")
    log_message(f"Incremental Sharpe: {overlay_test - base_test:+.3f}")
    
    if ALPHA_BB == 0.0:
        log_message("\n✅ PRODUCTION MODE: PEAD Only (Buyback weight = 0)")
        log_message("   Strategy is ready for production deployment")
    else:
        log_message(f"\n⚠️  R&D MODE: PEAD + Buyback (α_bb={ALPHA_BB})")
        log_message("   DO NOT deploy this configuration to production!")
    
    log_message("\n" + "=" * 80)
    log_message("ENSEMBLE ANALYSIS COMPLETE")
    log_message("=" * 80)
    log_message(f"Log file: {LOG_FILE}")


if __name__ == "__main__":
    main()
