#!/usr/bin/env python3
"""
Buyback Event Research (SP100)
Buyback 단독 알파 검증 + Label Shuffle
"""

import os
import sys
import numpy as np
import pandas as pd
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from research.pead.buyback_event_builder_v2 import build_buyback_events, convert_v6_to_standard
from research.pead.forward_return import attach_forward_returns


# Paths
BUYBACK_RAW_PATH = project_root / "data" / "buyback" / "buyback_events_sp100_full.csv"
BUYBACK_EVENTS_PATH = project_root / "data" / "buyback_events.csv"
PRICES_PATH = project_root / "data" / "prices.csv"
SPX_PATH = project_root / "data" / "fundamentals.csv"  # Placeholder for benchmark

OUTPUT_PREFIX = "buyback_research"

# Split config
REAL_EVAL_SPLIT = {
    "train": ("2016-01-01", "2019-12-31"),
    "val": ("2020-01-01", "2021-12-31"),
    "test": ("2022-01-01", "2025-12-31"),
}


def load_prices():
    """Load price matrix"""
    px_long = pd.read_csv(PRICES_PATH)
    px_long['timestamp'] = pd.to_datetime(px_long['timestamp']).dt.normalize()
    px = px_long.pivot(index='timestamp', columns='symbol', values='close')
    px = px.ffill().fillna(0)
    return px


def load_benchmark(px_index):
    """Load or create benchmark (SPX proxy)"""
    # Use equal-weight of all stocks as proxy
    px_long = pd.read_csv(PRICES_PATH)
    px_long['timestamp'] = pd.to_datetime(px_long['timestamp']).dt.normalize()
    px = px_long.pivot(index='timestamp', columns='symbol', values='close')
    px = px.ffill()  # Forward fill to remove NaN
    bm = px.mean(axis=1)
    bm = bm.ffill()  # Forward fill benchmark
    return bm


def summarize_buyback(events_with_returns: pd.DataFrame,
                      horizons=(10, 20, 40)) -> pd.DataFrame:
    """
    Buyback 이벤트 단위 성과 요약 (split / horizon별).
    bucket == 'bb_top' 만 사용.
    """
    rows = []
    for split in ["train", "val", "test"]:
        df_split = events_with_returns[
            (events_with_returns["split"] == split) &
            (events_with_returns["bucket"] == "bb_top")
        ]
        if df_split.empty:
            continue

        for h in horizons:
            col_er = f"excess_ret_{h}d"
            if col_er not in df_split.columns:
                continue

            x = df_split[col_er].dropna()
            if len(x) < 5:  # Relaxed from 20 to 5 for test data
                continue

            mean = x.mean()
            std = x.std()
            sharpe = mean / (std + 1e-9)
            t_stat = mean / (std / np.sqrt(len(x)) + 1e-9)
            win_rate = (x > 0).mean()

            rows.append({
                "split": split,
                "horizon": h,
                "n_events": len(x),
                "mean_excess_ret": mean,
                "std_excess_ret": std,
                "sharpe": sharpe,
                "t_stat": t_stat,
                "win_rate": win_rate,
            })

    return pd.DataFrame(rows)


def label_shuffle_buyback(events_with_returns: pd.DataFrame,
                          horizons=(10, 20, 40),
                          n_iter: int = 200,
                          random_state: int = 42) -> pd.DataFrame:
    """
    Label Shuffle (event_date 내에서 signal_rank를 셔플하여 bucket 재지정).
    Buyback 이벤트 알파의 우연성 검정용 p-value 계산.
    """
    rng = np.random.default_rng(random_state)

    base_summary = summarize_buyback(events_with_returns, horizons)

    # (split, horizon) -> [mean_excess_ret_shuffled...]
    dist_means = {}

    for _ in range(n_iter):
        shuffled = events_with_returns.copy()

        def shuffle_rank(x):
            vals = x["signal_rank"].values.copy()
            rng.shuffle(vals)
            x["signal_rank"] = vals
            return x

        shuffled = shuffled.groupby("event_date", group_keys=False).apply(shuffle_rank)

        # 새 bucket 재할당 (상위 10% = bb_top)
        def bucketize(r):
            if pd.isna(r):
                return "neutral"
            return "bb_top" if r >= 0.9 else "neutral"

        shuffled["bucket"] = shuffled["signal_rank"].apply(bucketize)

        summary_i = summarize_buyback(shuffled, horizons)
        for _, row in summary_i.iterrows():
            key = (row["split"], row["horizon"])
            dist_means.setdefault(key, []).append(row["mean_excess_ret"])

    records = []
    for _, row in base_summary.iterrows():
        key = (row["split"], row["horizon"])
        dist = np.array(dist_means.get(key, []))
        if dist.size == 0:
            continue

        obs = row["mean_excess_ret"]
        # Buyback은 양의 알파 기대 → obs가 셔플 분포보다 큰 비율
        p_val = (dist >= obs).mean()

        rec = row.to_dict()
        rec["p_value"] = p_val
        records.append(rec)

    return pd.DataFrame(records)


def main():
    print("=== Buyback Event Research (SP100) ===")
    
    # Check if raw buyback file exists
    if not BUYBACK_RAW_PATH.exists():
        print(f"Warning: {BUYBACK_RAW_PATH} not found")
        print("Using test data instead...")
        BUYBACK_RAW_PATH_ALT = project_root / "data" / "buyback" / "buyback_events_v6_test10.csv"
        if not BUYBACK_RAW_PATH_ALT.exists():
            raise FileNotFoundError(f"No buyback data found")
        raw_bb = pd.read_csv(BUYBACK_RAW_PATH_ALT)
        raw_bb = convert_v6_to_standard(raw_bb)
    else:
        raw_bb = pd.read_csv(BUYBACK_RAW_PATH)

    # 1) 가격/벤치마크 로드
    print("[1] Loading prices / benchmark...")
    px = load_prices()
    bm = load_benchmark(px.index)

    # 2) 이벤트 테이블 생성
    print("[2] Building buyback events...")
    events_bb = build_buyback_events(
        raw_bb_df=raw_bb,
        price_index=px.index,
        split_cfg=REAL_EVAL_SPLIT,
        use_mc_ratio=False,  # No marketcap data yet
    )

    # 저장
    events_bb.to_csv(BUYBACK_EVENTS_PATH, index=False)
    print(f"Saved buyback events to: {BUYBACK_EVENTS_PATH}")
    print(f"Total events: {len(events_bb)}")

    # 3) forward returns 부착
    print("[3] Attaching forward returns...")
    events_bb_renamed = events_bb.rename(columns={'ticker': 'symbol'})
    
    print(f"  Input events: {len(events_bb_renamed)}")
    print(f"  Event columns: {events_bb_renamed.columns.tolist()}")
    print(f"  Sample event: {events_bb_renamed.iloc[0][['event_date', 'symbol']].to_dict()}")
    print(f"  px shape: {px.shape}, bm shape: {bm.shape}")
    
    events_ret = attach_forward_returns(
        events=events_bb_renamed,
        px=px,
        bm=bm,
        horizons=(10, 20, 40),
    )
    
    # Note: forward_return already preserves split/bucket columns from events_bb_renamed
    print(f"  Events with returns: {len(events_ret)}, columns: {events_ret.columns.tolist()[:15]}")
    
    # Debug: Check excess_ret distribution
    for h in (10, 20, 40):
        col = f'excess_ret_{h}d'
        if col in events_ret.columns:
            valid = events_ret[col].dropna()
            print(f"  {col}: {len(valid)} valid values (mean: {valid.mean():.4f})")
    
    # Debug: Check bb_top with valid returns
    bb_top_ret = events_ret[(events_ret['bucket'] == 'bb_top') & events_ret['excess_ret_10d'].notna()]
    print(f"  bb_top with valid returns: {len(bb_top_ret)} (Train: {(bb_top_ret['split']=='train').sum()}, Val: {(bb_top_ret['split']=='val').sum()}, Test: {(bb_top_ret['split']=='test').sum()})")

    # 4) 이벤트 단위 요약
    print("[4] Summarizing buyback event performance...")
    
    if len(events_ret) == 0:
        print("  Warning: No events with returns!")
        return
    
    summary = summarize_buyback(events_ret, horizons=(10, 20, 40))
    print("\n=== Buyback Event Summary ===")
    if len(summary) == 0:
        print("  Warning: Summary is empty! Checking data...")
        # Show sample data
        sample = events_ret[events_ret['bucket'] == 'bb_top'].head(5)
        print(f"  Sample bb_top events:")
        print(sample[['event_date', 'symbol', 'split', 'bucket', 'excess_ret_10d', 'excess_ret_20d', 'excess_ret_40d']])
    else:
        print(summary)

    # 5) Label Shuffle
    print("\n[5] Running label shuffle...")
    shuffle_res = label_shuffle_buyback(events_ret, horizons=(10, 20, 40), n_iter=200)
    print("\n=== Label Shuffle Result ===")
    print(shuffle_res)

    # 6) 저장
    summary.to_csv(f"{OUTPUT_PREFIX}_event_stats.csv", index=False)
    shuffle_res.to_csv(f"{OUTPUT_PREFIX}_label_shuffle.csv", index=False)

    print(f"\nSaved buyback research outputs with prefix: {OUTPUT_PREFIX}")
    print("=== Done ===")


if __name__ == "__main__":
    main()
