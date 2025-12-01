# research/pead/run_ares8_overlay_v2.py

"""
ARES8 v1 Overlay Backtest (v2)

개선사항:
- base_type 옵션 추가 (equal_weight vs ares7)
- build_base_portfolio() 함수로 베이스 구조 분리
- 롱온리 + sum=1 normalize 공통 함수
- fee_rate=0 Gross Overlay 지원
"""

import pandas as pd
import numpy as np

from .config import (
    PRICES_PATHS,
    SPX_CLOSE_PATH,
    REAL_EVAL_SPLIT,
)
from .price_loader import load_price_matrix, load_benchmark
from .event_table_builder_v1 import build_eps_events
from .signal_builder import build_daily_signal
from .overlay_engine import apply_overlay_budget, compute_portfolio_returns

SF1_EPS_PATH = "/home/ubuntu/ares7-ensemble/data/sf1_eps.csv"
DEFAULT_ARES7_WEIGHTS_PATH = "/home/ubuntu/ares7-ensemble/data/ares7_base_weights.csv"

OUTPUT_PREFIX = "ares8_overlay"


def load_ares7_weights(path: str) -> pd.DataFrame:
    """
    ARES7 base weights CSV 로딩.
    기대 포맷:
        date, symbol, weight
    
    Returns:
        date x symbol DataFrame (weight)
    """
    df = pd.read_csv(path)
    if "date" not in df.columns:
        raise ValueError("base weights CSV에 'date' 컬럼이 필요합니다.")
    if "symbol" not in df.columns:
        raise ValueError("base weights CSV에 'symbol' 컬럼이 필요합니다.")
    if "weight" not in df.columns:
        raise ValueError("base weights CSV에 'weight' 컬럼이 필요합니다.")

    df["date"] = pd.to_datetime(df["date"])
    w = df.pivot(index="date", columns="symbol", values="weight").sort_index()
    w = w.fillna(0.0)
    return w


def build_equal_weight_base(px: pd.DataFrame) -> pd.DataFrame:
    """
    Equal-Weight 베이스 포트폴리오 생성.
    
    Args:
        px: date x symbol 가격 DataFrame
    
    Returns:
        date x symbol weight DataFrame (동일 비중)
    """
    w_list = []
    for dt, row in px.iterrows():
        valid = row.dropna()
        if valid.empty:
            continue
        n = len(valid)
        w = pd.Series(1.0 / n, index=valid.index)
        w_df = pd.DataFrame({
            "date": [dt] * n,
            "symbol": w.index,
            "weight": w.values,
        })
        w_list.append(w_df)
    
    if not w_list:
        raise ValueError("No valid weights generated from price data.")
    
    w_all = pd.concat(w_list, ignore_index=True)
    w_all["date"] = pd.to_datetime(w_all["date"])
    w = w_all.pivot(index="date", columns="symbol", values="weight").sort_index()
    w = w.fillna(0.0)
    return w


def normalize_weights(w: pd.DataFrame, long_only: bool = True) -> pd.DataFrame:
    """
    Weight 정규화: 롱온리 제약 + sum=1 정규화.
    
    Args:
        w: date x symbol weight DataFrame
        long_only: True이면 음수 weight를 0으로 클리핑
    
    Returns:
        정규화된 weight DataFrame
    """
    if long_only:
        w = w.clip(lower=0.0)
    
    # 날짜별 sum=1 정규화
    ssum = w.sum(axis=1).replace(0, np.nan)
    w = w.div(ssum, axis=0).fillna(0.0)
    return w


def build_base_portfolio(
    base_type: str,
    px: pd.DataFrame,
    ares7_weights_path: str = None,
) -> pd.DataFrame:
    """
    베이스 포트폴리오 생성.
    
    Args:
        base_type: "equal_weight" 또는 "ares7"
        px: date x symbol 가격 DataFrame
        ares7_weights_path: ARES7 weight CSV 경로 (base_type="ares7"일 때 필요)
    
    Returns:
        date x symbol weight DataFrame
    """
    if base_type == "equal_weight":
        print("Building Equal-Weight base portfolio...")
        w_base = build_equal_weight_base(px)
    elif base_type == "ares7":
        if ares7_weights_path is None:
            ares7_weights_path = DEFAULT_ARES7_WEIGHTS_PATH
        print(f"Loading ARES7 base weights from {ares7_weights_path}...")
        w_base = load_ares7_weights(ares7_weights_path)
    else:
        raise ValueError(f"Unknown base_type: {base_type}")
    
    # 정규화
    w_base = normalize_weights(w_base, long_only=True)
    return w_base


def compute_stats(ret: pd.Series, name: str, split_cfg: dict) -> pd.DataFrame:
    """
    Sharpe, 연환산 수익/변동성, MDD를 전체/스플릿별로 계산.
    """
    def _stats(series: pd.Series):
        series = series.dropna()
        if len(series) < 10:
            return {
                "n_days": len(series),
                "ann_return": np.nan,
                "ann_vol": np.nan,
                "sharpe": np.nan,
                "mdd": np.nan,
            }
        mean = series.mean()
        vol = series.std()
        ann_ret = mean * 252
        ann_vol = vol * np.sqrt(252)
        sharpe = (mean / (vol + 1e-9)) * np.sqrt(252)
        # MDD
        curve = (1 + series).cumprod()
        peak = curve.cummax()
        dd = curve / peak - 1
        mdd = dd.min()
        return {
            "n_days": len(series),
            "ann_return": ann_ret,
            "ann_vol": ann_vol,
            "sharpe": sharpe,
            "mdd": mdd,
        }

    rows = []

    # 전체
    s_all = _stats(ret)
    s_all.update({"name": name, "split": "all"})
    rows.append(s_all)

    # split 단위
    for split_name, (start, end) in split_cfg.items():
        mask = (ret.index >= start) & (ret.index <= end)
        s = _stats(ret[mask])
        s.update({"name": name, "split": split_name})
        rows.append(s)

    return pd.DataFrame(rows)


def main(
    base_type: str = "equal_weight",
    ares7_weights_path: str = None,
    horizon: int = 5,
    budget: float = 0.1,
    fee_rate: float = 0.001,
    mode: str = "strength",
    min_rank: float = 0.8,
):
    """
    ARES8 v1 Overlay 백테스트 메인 함수.
    
    Args:
        base_type: "equal_weight" 또는 "ares7"
        ares7_weights_path: ARES7 weight CSV 경로 (base_type="ares7"일 때)
        horizon: PEAD holding horizon (days)
        budget: Overlay budget (0~1)
        fee_rate: One-way transaction fee rate
        mode: Overlay weight mode ("strength" or "equal")
        min_rank: Minimum surprise_rank threshold (0~1)
    """
    print("=== ARES8 v1 Overlay Backtest (v2) ===")
    print(f"Base={base_type}, Horizon={horizon}, Budget={budget}, fee_rate={fee_rate}, mode={mode}, min_rank={min_rank}")

    # 1) 가격 데이터 로딩
    print("Loading prices...")
    px = load_price_matrix(PRICES_PATHS)

    # 2) 베이스 포트폴리오 생성
    w_base = build_base_portfolio(
        base_type=base_type,
        px=px,
        ares7_weights_path=ares7_weights_path,
    )

    # 3) EPS 이벤트 로딩
    print("Building EPS events...")
    events = build_eps_events(
        SF1_EPS_PATH,
        price_index=px.index,
        split_cfg=REAL_EVAL_SPLIT,
    )
    events = events.rename(columns={"ticker": "symbol"})
    print(f"Total EPS events: {len(events)}")

    # 4) 공통 유니버스/날짜 align
    common_dates = px.index.intersection(w_base.index)
    common_symbols = sorted(set(px.columns) & set(w_base.columns))

    px = px.reindex(index=common_dates, columns=common_symbols)
    w_base = w_base.reindex(index=common_dates, columns=common_symbols).fillna(0.0)

    # 5) PEAD 시그널 생성
    print("Building daily PEAD signal...")
    signal = build_daily_signal(
        events=events,
        price_index=px.index,
        horizon=horizon,
        bucket_col="bucket",
        rank_col="surprise_rank",
        min_rank=min_rank,
    )
    signal = signal.reindex(index=common_dates, columns=common_symbols).fillna(0.0)

    # 6) Overlay 계산
    print("Applying overlay budget...")
    w_overlay = apply_overlay_budget(
        w_base=w_base,
        signal=signal,
        budget=budget,
        mode=mode,
        cap_single=0.05,
    )

    # 7) 포트폴리오 수익률 계산
    print("Computing portfolio returns...")
    base_ret = compute_portfolio_returns(w_base, px, fee_rate=fee_rate)
    overlay_ret = compute_portfolio_returns(w_overlay, px, fee_rate=fee_rate)
    incr_ret = overlay_ret - base_ret

    # 8) 성능 통계
    print("Summarizing performance stats...")
    stats_base = compute_stats(base_ret, "base", REAL_EVAL_SPLIT)
    stats_overlay = compute_stats(overlay_ret, "overlay", REAL_EVAL_SPLIT)
    stats_incr = compute_stats(incr_ret, "incremental", REAL_EVAL_SPLIT)

    stats_all = pd.concat([stats_base, stats_overlay, stats_incr], ignore_index=True)
    print(stats_all)

    # 9) 결과 저장
    stats_all.to_csv(f"{OUTPUT_PREFIX}_stats.csv", index=False)
    base_ret.to_csv(f"{OUTPUT_PREFIX}_base_ret.csv")
    overlay_ret.to_csv(f"{OUTPUT_PREFIX}_overlay_ret.csv")
    incr_ret.to_csv(f"{OUTPUT_PREFIX}_incremental_ret.csv")

    print(f"\nSaved overlay results with prefix: {OUTPUT_PREFIX}_*")
    print("=== Done ===")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="ARES8 v1 Overlay Backtest (v2)")
    parser.add_argument("--base_type", type=str, default="equal_weight",
                        choices=["equal_weight", "ares7"],
                        help="Base portfolio type (default: equal_weight)")
    parser.add_argument("--ares7_weights_path", type=str, default=None,
                        help="Path to ARES7 base weights CSV (required if base_type=ares7)")
    parser.add_argument("--budget", type=float, default=0.1,
                        help="Overlay budget (default: 0.10)")
    parser.add_argument("--horizon", type=int, default=5,
                        help="PEAD holding horizon in days (default: 5)")
    parser.add_argument("--fee", type=float, default=0.001,
                        help="One-way transaction fee rate (default: 0.001)")
    parser.add_argument("--mode", type=str, default="strength",
                        choices=["strength", "equal"],
                        help="Overlay weight mode (strength/equal)")
    parser.add_argument("--min_rank", type=float, default=0.8,
                        help="Minimum surprise_rank threshold (default: 0.8)")

    args = parser.parse_args()

    main(
        base_type=args.base_type,
        ares7_weights_path=args.ares7_weights_path,
        horizon=args.horizon,
        budget=args.budget,
        fee_rate=args.fee,
        mode=args.mode,
        min_rank=args.min_rank,
    )
