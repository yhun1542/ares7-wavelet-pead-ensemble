#!/usr/bin/env python3
"""
ARES-7 DeepMind Enhanced v1 (Rebuilt)
--------------------------------------
- 입력:  price CSV (timestamp, symbol, close)
- 출력:  JSON (sharpe, annual_return, annual_volatility, max_drawdown, daily_returns)
- 실행:
    python3.11 engine_enhanced_v1_deepmind.py \
        --price data/price_full.csv \
        --output results/engine_enhanced_v1_deepmind.json

핵심 아이디어:
- Kalman Filter로 가격 노이즈 제거
- Hurst 기반 레짐 감지 (Trend vs Mean-Reversion)
- Residual Momentum (시장 베타 제거)
- Mean-Reversion (Kalman Z-score 기반)
- Skewness Preference (복권형 종목 기피)
- Weekly L/S 포트폴리오, Gross=2.0
- Vol Targeting (12%) + 거래비용 반영
- Look-ahead 완전 제거
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

TRADING_DAYS = 252

CONFIG = {
    # 시그널 파라미터
    "momentum_lookback": 120,
    "momentum_skip": 5,
    "mean_reversion_lookback": 20,
    "skew_lookback": 60,
    "hurst_lookback": 126,

    # 포트폴리오 파라미터
    "n_long": 15,
    "n_short": 15,
    "gross_exposure": 2.0,
    "rebalance_freq": "W-FRI",   # 주간 리밸

    # 리스크 관리
    "tc_bps": 5,                 # 거래비용 5 bps (0.05%)
    "target_vol": 0.12,          # 엔진 레벨 목표 변동성 12%
    "vol_lookback": 60,
    "min_leverage": 0.5,
    "max_leverage": 2.0,
}


# ---------------------------------------------------------------------
# 유틸 함수
# ---------------------------------------------------------------------
def zscore(s: pd.Series) -> pd.Series:
    s = s.replace([np.inf, -np.inf], np.nan)
    m = s.mean()
    v = s.std()
    if v == 0 or np.isnan(v):
        return s * 0.0
    return (s - m) / v


def load_price(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.normalize()
    df = df.sort_values(["timestamp", "symbol"])
    price = df.pivot(index="timestamp", columns="symbol", values="close")
    return price


# ---------------------------------------------------------------------
# Kalman Filter & Hurst 계산
# ---------------------------------------------------------------------
def kalman_filter_1d(series: pd.Series, obs_cov=1.0, trans_cov=0.05) -> pd.Series:
    """
    단일 자산에 Kalman 필터 적용 (상태 1차원)
    """
    n = len(series)
    if n == 0:
        return series

    state_mean = np.zeros(n)
    state_cov = np.zeros(n)

    state_mean[0] = series.iloc[0]
    state_cov[0] = 1.0

    for i in range(1, n):
        prior_mean = state_mean[i - 1]
        prior_cov = state_cov[i - 1] + trans_cov

        # Kalman gain
        k = prior_cov / (prior_cov + obs_cov)

        state_mean[i] = prior_mean + k * (series.iloc[i] - prior_mean)
        state_cov[i] = (1 - k) * prior_cov

    return pd.Series(state_mean, index=series.index)


def compute_hurst(series: pd.Series, window: int) -> pd.Series:
    """
    단일 자산 Hurst 지수 계산 (롤링 R/S)
    """
    def rs_hurst(x: np.ndarray) -> float:
        if len(x) < window:
            return 0.5
        try:
            n = len(x)
            mean = np.mean(x)
            dev = np.cumsum(x - mean)
            R = np.max(dev) - np.min(dev)
            S = np.std(x, ddof=1)
            if S == 0:
                return 0.5
            RS = R / S
            H = np.log(RS) / np.log(n)
            return float(np.clip(H, 0.2, 0.8))
        except Exception:
            return 0.5

    return series.rolling(window).apply(rs_hurst, raw=True)


# ---------------------------------------------------------------------
# 시그널 생성
# ---------------------------------------------------------------------
def build_signals(price: pd.DataFrame, config: dict):
    """
    Kalman, Hurst, Residual Momentum, Mean-Reversion, Skewness 기반 복합 시그널 생성
    반환: composite_signal (DataFrame, index=dates, columns=symbols)
    """
    price = price.sort_index()
    returns = price.pct_change()

    # Kalman 필터 가격
    print("  Applying Kalman filter...")
    kalman_prices = price.apply(
        kalman_filter_1d,
        obs_cov=config.get("kalman_obs_cov", 1.0),
        trans_cov=config.get("kalman_trans_cov", 0.05)
    )
    kalman_returns = kalman_prices.pct_change()

    # Hurst 지수
    print("  Computing Hurst exponent...")
    hurst = returns.apply(
        compute_hurst,
        window=config["hurst_lookback"]
    )

    # 1) Residual Momentum (시장 평균 제거)
    print("  Building residual momentum signal...")
    look = config["momentum_lookback"]
    skip = config["momentum_skip"]
    # (1 + r).prod - 1 방식으로 120일 모멘텀, 직전 5일 제거
    cum_ret = (1 + returns).rolling(look).apply(lambda x: np.prod(1 + x) - 1, raw=True)
    skip_ret = (1 + returns).rolling(skip).apply(lambda x: np.prod(1 + x) - 1, raw=True)
    mom_raw = cum_ret - skip_ret

    # 시장 수익률 = 단순 평균
    market_mom = mom_raw.mean(axis=1)
    resid_mom = mom_raw.sub(market_mom, axis=0)

    # Hurst 기반 강화 (트렌드 레짐)
    hurst_trend_flag = (hurst > 0.55).astype(float)
    resid_mom_adj = resid_mom * (0.5 + 0.5 * hurst_trend_flag)

    # 2) Mean-Reversion (Kalman z-score)
    print("  Building mean-reversion signal...")
    mr_lb = config["mean_reversion_lookback"]
    mean_k = kalman_prices.rolling(mr_lb).mean()
    std_k = kalman_prices.rolling(mr_lb).std().replace(0, np.nan)
    z_k = (kalman_prices - mean_k) / std_k
    mean_rev_raw = -z_k  # 고평가 숏, 저평가 롱

    # Hurst 기반 강화 (Mean-Reverting 레짐)
    hurst_rev_flag = (hurst < 0.45).astype(float)
    mean_rev_adj = mean_rev_raw * (0.5 + 0.5 * hurst_rev_flag)

    # 3) Skewness Preference (복권형 회피)
    print("  Building skewness preference signal...")
    skew_lb = config["skew_lookback"]
    skew = returns.rolling(skew_lb).skew()
    skew_pref = -skew  # 양의 왜도(로또형) 회피

    # 4) Cross-sectional rank normalization & 결합
    print("  Combining signals...")
    def cs_rank(df: pd.DataFrame) -> pd.DataFrame:
        # 일별 cross-sectional rank → -0.5 ~ +0.5
        return df.rank(axis=1, pct=True) - 0.5

    mom_cs = cs_rank(resid_mom_adj)
    mr_cs = cs_rank(mean_rev_adj)
    skew_cs = cs_rank(skew_pref)

    # 가중치 (Jason 전략 문서 기준: 모멘텀 비중 높게) :contentReference[oaicite:3]{index=3}
    w_mom = 0.4
    w_mr = 0.3
    w_skew = 0.3

    composite = (
        w_mom * mom_cs +
        w_mr * mr_cs +
        w_skew * skew_cs
    )

    # Look-ahead 제거: 모든 시그널을 1일 시프트
    composite = composite.shift(1)

    return composite


# ---------------------------------------------------------------------
# 백테스트
# ---------------------------------------------------------------------
def backtest_ls_engine(price: pd.DataFrame,
                       signal: pd.DataFrame,
                       config: dict):
    """
    Long/Short 엔진 백테스트
    - Long n_long, Short n_short
    - Gross exposure = 2.0
    - Weekly rebalance (config["rebalance_freq"])
    - Vol targeting + 거래비용
    """
    price = price.sort_index()
    returns = price.pct_change()
    dates = price.index
    symbols = price.columns

    n_long = config["n_long"]
    n_short = config["n_short"]
    gross = config["gross_exposure"]
    tc_bps = config["tc_bps"]

    # 리밸 날짜 (예: W-FRI)
    rebal_dates = price.resample(config["rebalance_freq"]).last().index
    rebal_dates = [d for d in rebal_dates if d in dates]

    current_w = pd.Series(0.0, index=symbols)
    weight_history = []
    pnl_list = []

    for i, d in enumerate(dates):
        if i == 0:
            pnl_list.append(0.0)
            continue

        cost = 0.0

        if d in rebal_dates:
            # 이 날짜에 사용할 시그널 (이미 shift(1)돼 있으므로 d는 d-1까지 정보 기반)
            if d in signal.index:
                sig_row = signal.loc[d].dropna()
            else:
                sig_row = pd.Series(dtype=float)

            if len(sig_row) >= n_long + n_short:
                sig_sorted = sig_row.sort_values(ascending=False)
                long_names = sig_sorted.head(n_long).index
                short_names = sig_sorted.tail(n_short).index

                w_new = pd.Series(0.0, index=symbols)
                w_long = (gross / 2.0) / n_long
                w_short = -(gross / 2.0) / n_short

                w_new.loc[long_names] = w_long
                w_new.loc[short_names] = w_short

                # 거래비용 (turnover 기반)
                if weight_history:
                    prev = weight_history[-1]
                    turnover = (w_new - prev).abs().sum() / 2.0
                    cost = turnover * (tc_bps / 10000.0)

                current_w = w_new
                weight_history.append(current_w.copy())

        # 일일 수익
        r_t = returns.loc[d]
        pnl_t = float((current_w * r_t).sum()) - cost
        pnl_list.append(pnl_t)

    pnl = pd.Series(pnl_list, index=dates).fillna(0.0)

    # Vol targeting
    vol_lb = config["vol_lookback"]
    target_vol = config["target_vol"]
    realized_vol = pnl.rolling(vol_lb).std() * np.sqrt(TRADING_DAYS)
    lev = target_vol / realized_vol.replace(0, target_vol)
    lev = lev.shift(1).clip(config["min_leverage"], config["max_leverage"]).fillna(1.0)

    pnl_vt = pnl * lev

    # 성과 지표
    r = pnl_vt.dropna()
    if len(r) == 0:
        sharpe = ann_ret = ann_vol = mdd = 0.0
    else:
        ann_ret = r.mean() * TRADING_DAYS
        ann_vol = r.std() * np.sqrt(TRADING_DAYS)
        sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0

        cum = (1 + r).cumprod()
        peak = cum.cummax()
        dd = cum / peak - 1.0
        mdd = dd.min()

    result = {
        "sharpe": float(sharpe),
        "annual_return": float(ann_ret),
        "annual_volatility": float(ann_vol),
        "max_drawdown": float(mdd),
        "daily_returns": pnl_vt.tolist(),
        "dates": [d.strftime("%Y-%m-%d") for d in pnl_vt.index],
    }
    return result


# ---------------------------------------------------------------------
# main
# ---------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="ARES-7 DeepMind Enhanced v1 (Rebuilt)")
    parser.add_argument("--price", type=str, required=True,
                        help="Path to price_full.csv (timestamp, symbol, close)")
    parser.add_argument("--output", type=str, required=True,
                        help="Path to output JSON file")
    args = parser.parse_args()

    print("=" * 70)
    print("ARES-7 DeepMind Enhanced v1 (Rebuilt)")
    print("=" * 70)
    print(f"Price file : {args.price}")
    print(f"Output file: {args.output}")
    print("=" * 70)

    # 1) 데이터 로드
    print("Loading price data...")
    price = load_price(args.price)
    print(f"  Data shape: {price.shape[0]} days, {price.shape[1]} symbols")

    # 2) 시그널 생성
    print("\nBuilding signals...")
    composite_signal = build_signals(price, CONFIG)

    # 3) 백테스트
    print("\nRunning backtest...")
    results = backtest_ls_engine(price, composite_signal, CONFIG)

    print("\nPerformance Summary")
    print("-------------------")
    print(f"  Sharpe          : {results['sharpe']:.3f}")
    print(f"  Annual Return   : {results['annual_return']*100:.2f}%")
    print(f"  Annual Volatility: {results['annual_volatility']*100:.2f}%")
    print(f"  Max Drawdown    : {results['max_drawdown']*100:.2f}%")

    # 출력 JSON 최소 형식 유지 (요청 형식) :contentReference[oaicite:4]{index=4}
    out_obj = {
        "sharpe": results["sharpe"],
        "annual_return": results["annual_return"],
        "annual_volatility": results["annual_volatility"],
        "max_drawdown": results["max_drawdown"],
        "daily_returns": results["daily_returns"],
        # dates는 추가 정보 (기존 시스템과 호환 위해 넣어둠)
        "dates": results["dates"],
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out_obj, f, indent=2)

    print(f"\nSaved JSON to {out_path}")
    print("=" * 70)


if __name__ == "__main__":
    main()