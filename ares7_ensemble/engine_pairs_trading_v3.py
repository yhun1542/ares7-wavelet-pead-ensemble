#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine_pairs_trading_v3.py

Pairs Trading v3:
- v1의 고정 헷지 비율 유지 ✅
- 볼린저 밴드 기반 진입/청산 (AI 제안)
- 손절매 로직 (AI 제안)
"""

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import json
from datetime import datetime

# 설정
LOOKBACK_HEDGE = None  # 전체 기간 고정 헷지
LOOKBACK_BB = 20  # 볼린저 밴드 윈도우
BB_STD = 2.0  # 볼린저 밴드 표준편차 배수
ZSCORE_STOPLOSS = 3.5  # 손절매 Z-Score 임계값
TIME_STOPLOSS = 60  # 시간 기반 손절매 (거래일)

def load_data(pair_name):
    """페어 데이터 로드"""
    df = pd.read_csv("data/pairs_price.csv", parse_dates=["timestamp"])
    
    ticker1, ticker2 = pair_name.split("/")
    
    # Pivot to wide format
    df_pivot = df.pivot(index="timestamp", columns="symbol", values="close")
    df_pivot = df_pivot.sort_index()
    
    if ticker1 not in df_pivot.columns or ticker2 not in df_pivot.columns:
        raise ValueError(f"Ticker {ticker1} or {ticker2} not found in data")
    
    result = pd.DataFrame({
        "P1": df_pivot[ticker1],
        "P2": df_pivot[ticker2]
    }).dropna()
    
    return result

def calculate_fixed_hedge_ratio(df):
    """고정 헷지 비율 계산 (전체 기간 OLS)"""
    log_p1 = np.log(df["P1"])
    log_p2 = np.log(df["P2"])
    
    X = log_p2.values.reshape(-1, 1)
    y = log_p1.values.reshape(-1, 1)
    
    model = LinearRegression()
    model.fit(X, y)
    beta = model.coef_[0][0]
    
    return beta

def calculate_spread(df, hedge_ratio):
    """스프레드 계산"""
    log_p1 = np.log(df["P1"])
    log_p2 = np.log(df["P2"])
    spread = log_p1 - hedge_ratio * log_p2
    return spread

def calculate_bollinger_bands(spread, lookback=20, std_mult=2.0):
    """볼린저 밴드 계산"""
    ma = spread.rolling(lookback).mean()
    std = spread.rolling(lookback).std()
    
    upper = ma + std_mult * std
    lower = ma - std_mult * std
    
    return ma, upper, lower

def calculate_zscore(spread, lookback=60):
    """Z-Score 계산 (손절매용)"""
    ma = spread.rolling(lookback).mean()
    std = spread.rolling(lookback).std()
    zscore = (spread - ma) / std
    return zscore

def backtest_pairs_v3(pair_name):
    """Pairs Trading v3 백테스트"""
    print(f"\n{'='*80}")
    print(f"Pairs Trading v3: {pair_name}")
    print(f"{'='*80}")
    
    # 데이터 로드
    df = load_data(pair_name)
    print(f"데이터 기간: {df.index[0].date()} ~ {df.index[-1].date()} ({len(df)} 거래일)")
    
    # 고정 헷지 비율 계산
    print(f"\n1. 고정 헷지 비율 계산 (전체 기간 OLS)...")
    hedge_ratio = calculate_fixed_hedge_ratio(df)
    print(f"   헷지 비율: {hedge_ratio:.4f}")
    
    # 스프레드 계산
    spread = calculate_spread(df, hedge_ratio)
    
    # 볼린저 밴드 계산
    print(f"2. 볼린저 밴드 계산 ({LOOKBACK_BB}일, {BB_STD}σ)...")
    ma, upper, lower = calculate_bollinger_bands(spread, LOOKBACK_BB, BB_STD)
    
    # Z-Score 계산 (손절매용)
    zscore = calculate_zscore(spread, 60)
    
    # 백테스트
    print(f"3. 백테스트 실행...")
    position = pd.Series(0.0, index=df.index)
    entry_date = pd.Series(pd.NaT, index=df.index)
    
    for i in range(LOOKBACK_BB, len(df)):
        date = df.index[i]
        
        # 현재 포지션 확인
        current_pos = position.iloc[i-1]
        
        if current_pos == 0:
            # 진입 조건: 볼린저 밴드 돌파
            if spread.iloc[i] > upper.iloc[i]:
                # 스프레드가 상단 밴드 돌파 → 숏 (스프레드 하락 예상)
                position.iloc[i] = -1.0
                entry_date.iloc[i] = date
            elif spread.iloc[i] < lower.iloc[i]:
                # 스프레드가 하단 밴드 돌파 → 롱 (스프레드 상승 예상)
                position.iloc[i] = 1.0
                entry_date.iloc[i] = date
            else:
                position.iloc[i] = 0
        else:
            # 청산 조건
            days_held = (date - entry_date.iloc[i-1]).days if pd.notna(entry_date.iloc[i-1]) else 0
            
            # 1) 정상 청산: 중심선(MA) 회귀
            if current_pos > 0 and spread.iloc[i] >= ma.iloc[i]:
                position.iloc[i] = 0
                entry_date.iloc[i] = pd.NaT
            elif current_pos < 0 and spread.iloc[i] <= ma.iloc[i]:
                position.iloc[i] = 0
                entry_date.iloc[i] = pd.NaT
            # 2) 손절매: Z-Score 극단값
            elif abs(zscore.iloc[i]) > ZSCORE_STOPLOSS:
                position.iloc[i] = 0
                entry_date.iloc[i] = pd.NaT
            # 3) 시간 기반 손절매
            elif days_held > TIME_STOPLOSS:
                position.iloc[i] = 0
                entry_date.iloc[i] = pd.NaT
            else:
                position.iloc[i] = current_pos
                entry_date.iloc[i] = entry_date.iloc[i-1]
    
    # 수익률 계산
    spread_return = spread.diff()
    strategy_return = position.shift(1) * spread_return
    strategy_return = strategy_return.fillna(0)
    
    # 누적 수익률
    cumulative_return = (1 + strategy_return).cumprod()
    
    # 성과 지표
    total_return = cumulative_return.iloc[-1] - 1
    annual_return = (1 + total_return) ** (252 / len(df)) - 1
    annual_vol = strategy_return.std() * np.sqrt(252)
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0
    
    cumulative_max = cumulative_return.cummax()
    drawdown = (cumulative_return - cumulative_max) / cumulative_max
    max_drawdown = drawdown.min()
    
    # 거래 통계
    trades = (position.diff() != 0).sum()
    avg_turnover = trades / len(df) * 100
    avg_position = abs(position).mean()
    
    print(f"\n{'='*80}")
    print(f"백테스트 결과")
    print(f"{'='*80}")
    print(f"Sharpe Ratio: {sharpe:.3f}")
    print(f"Annual Return: {annual_return*100:.2f}%")
    print(f"Annual Volatility: {annual_vol*100:.2f}%")
    print(f"Max Drawdown: {max_drawdown*100:.2f}%")
    print(f"Total Trades: {trades}")
    print(f"Avg Turnover: {avg_turnover:.2f}%")
    print(f"Avg Position: {avg_position:.2f}")
    print(f"{'='*80}\n")
    
    # 결과 저장
    results = {
        "pair": pair_name,
        "start_date": df.index[0].strftime("%Y-%m-%d"),
        "end_date": df.index[-1].strftime("%Y-%m-%d"),
        "trading_days": len(df),
        "sharpe": float(sharpe),
        "annual_return": float(annual_return),
        "annual_volatility": float(annual_vol),
        "max_drawdown": float(max_drawdown),
        "total_trades": int(trades),
        "avg_turnover": float(avg_turnover),
        "avg_position": float(avg_position),
        "returns": strategy_return.tolist(),
        "dates": [d.strftime("%Y-%m-%d") for d in df.index]
    }
    
    return results

def main():
    pairs = ["KO/PEP", "GLD/SLV", "XOM/CVX", "MS/GS"]
    
    all_results = {}
    
    for pair in pairs:
        try:
            results = backtest_pairs_v3(pair)
            all_results[pair.replace("/", "_")] = results
            
            # 개별 결과 저장
            output_file = f"results/engine_pairs_trading_v3_{pair.replace('/', '_')}.json"
            with open(output_file, "w") as f:
                json.dump(results, f, indent=2)
            print(f"✅ 결과 저장: {output_file}")
        except Exception as e:
            print(f"❌ {pair} 오류: {e}")
    
    # 전체 결과 요약
    print(f"\n{'='*80}")
    print("Pairs Trading v3 전체 결과 요약")
    print(f"{'='*80}")
    print(f"{'Pair':<15} {'Sharpe':>8} {'Return':>8} {'Vol':>8} {'MDD':>8}")
    print(f"{'-'*80}")
    for pair, res in all_results.items():
        print(f"{pair:<15} {res['sharpe']:>8.3f} {res['annual_return']*100:>7.2f}% {res['annual_volatility']*100:>7.2f}% {res['max_drawdown']*100:>7.2f}%")
    print(f"{'='*80}\n")

if __name__ == "__main__":
    main()
