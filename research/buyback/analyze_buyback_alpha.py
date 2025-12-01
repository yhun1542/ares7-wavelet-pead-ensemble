#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Analyze buyback announcement alpha:
- H-day forward returns
- Train/Val/Test split
- Sharpe / mean / std
- Output: CSV summary

Usage:

python -m research.buyback.analyze_buyback_alpha \
    --events data/buyback/buyback_events.parquet \
    --returns data/prices/returns.parquet \
    --output data/buyback/buyback_alpha_summary.csv \
    --horizons 3 5 10 15 20
"""

import argparse
import pandas as pd
import numpy as np
from pathlib import Path


# --------------------------------------------------------------------------- #
# Utilities
# --------------------------------------------------------------------------- #

def compute_forward_return(returns: pd.DataFrame, start_date, symbol: str, horizon: int):
    """
    returns: date-indexed, symbol columns, daily simple returns (NOT log)
    start_date: event date (use T+1 ~ T+H)
    """
    try:
        idx = returns.index.get_loc(start_date)
    except KeyError:
        idx = returns.index.searchsorted(start_date)
        if idx >= len(returns.index):
            return np.nan

    start_idx = idx + 1
    end_idx = start_idx + horizon
    if end_idx > len(returns.index):
        return np.nan

    if symbol not in returns.columns:
        return np.nan

    r = returns.iloc[start_idx:end_idx][symbol]
    if r.isnull().any():
        return np.nan

    return float((1.0 + r).prod() - 1.0)


def calc_stats(series):
    """Return mean, std, sharpe for a vector."""
    arr = np.array(series, dtype=float)
    arr = arr[~np.isnan(arr)]
    if len(arr) == 0:
        return np.nan, np.nan, np.nan
    
    mean = arr.mean()
    std = arr.std(ddof=1)
    sharpe = mean / std if std > 0 else np.nan
    return mean, std, sharpe


# --------------------------------------------------------------------------- #
# Main Logic
# --------------------------------------------------------------------------- #

def analyze_buyback_alpha(events: pd.DataFrame,
                          returns: pd.DataFrame,
                          horizons,
                          train_end,
                          val_end):
    """
    events: DataFrame(date, symbol, ...)
    returns: daily returns (date index, symbol columns)
    """
    events = events.copy()
    events["date"] = pd.to_datetime(events["date"])
    
    train_end = pd.to_datetime(train_end)
    val_end = pd.to_datetime(val_end)
    
    rows = []

    splits = {
        "All": events.index,
        "Train": events["date"] <= train_end,
        "Val": (events["date"] > train_end) & (events["date"] <= val_end),
        "Test": events["date"] > val_end,
    }

    for H in horizons:
        for split_name, mask in splits.items():
            ev = events[mask]
            if len(ev) == 0:
                continue
            
            rets_H = []
            for _, row in ev.iterrows():
                rH = compute_forward_return(
                    returns=returns,
                    start_date=row["date"],
                    symbol=row["symbol"],
                    horizon=H,
                )
                rets_H.append(rH)
            
            mean, std, sharpe = calc_stats(rets_H)
            
            rows.append({
                "horizon": H,
                "split": split_name,
                "n_events": len(ev),
                "mean_ret": mean,
                "std_ret": std,
                "sharpe": sharpe,
            })
    
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args():
    p = argparse.ArgumentParser(description="Analyze H-day alpha for buyback announcements.")
    p.add_argument("--events", type=str, required=True)
    p.add_argument("--returns", type=str, required=True)
    p.add_argument("--output", type=str, required=True)
    p.add_argument("--horizons", type=int, nargs="+", default=[3, 5, 10, 15, 20])
    p.add_argument("--train_end", type=str, default="2018-12-31")
    p.add_argument("--val_end", type=str, default="2021-12-31")
    return p.parse_args()


def main():
    args = parse_args()

    # Load events
    if args.events.endswith(".parquet"):
        events = pd.read_parquet(args.events)
    else:
        events = pd.read_csv(args.events, parse_dates=["date"])

    # Load returns
    if args.returns.endswith(".parquet"):
        returns = pd.read_parquet(args.returns)
    else:
        returns = pd.read_csv(args.returns, parse_dates=["date"]).set_index("date")

    df = analyze_buyback_alpha(
        events=events,
        returns=returns,
        horizons=args.horizons,
        train_end=args.train_end,
        val_end=args.val_end,
    )

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    print(f"Saved buyback alpha summary → {out} (n={len(df)})")


if __name__ == "__main__":
    main()
