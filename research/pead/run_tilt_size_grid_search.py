#!/usr/bin/env python3
"""
Tilt Size Grid Search
Horizon 고정 (20d), Tilt Size 변화 [0.5%p, 0.75%p, 1.0%p, 1.25%p, 1.5%p]
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path
import json

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from research.pead.event_book import EventBook, backtest_pure_tilt

print("="*80)
print("Tilt Size Grid Search")
print("="*80)

# 1. Load data
print("\n[1/4] 데이터 로딩...")
px_long = pd.read_csv(project_root / "data" / "prices.csv")
px_long['timestamp'] = pd.to_datetime(px_long['timestamp'])
px = px_long.pivot(index='timestamp', columns='symbol', values='close')
px = px.ffill().fillna(0)

w_base_long = pd.read_csv(project_root / "data" / "ares7_base_weights.csv", parse_dates=['date'])
w_base = w_base_long.pivot(index='date', columns='symbol', values='weight')
w_base = w_base.fillna(0)

events = pd.read_csv(project_root / "data" / "pead_event_table_positive.csv", parse_dates=['date'])

print(f"  Prices: {px.shape}")
print(f"  Base weights: {w_base.shape}")
print(f"  Events: {len(events)}")

# 2. Create signal
print("\n[2/4] 시그널 생성...")
signal = pd.DataFrame(0, index=px.index, columns=px.columns)

for _, row in events.iterrows():
    event_date = row['date']
    symbol = row['symbol']
    if symbol not in signal.columns:
        continue
    future_dates = px.index[px.index >= event_date]
    if len(future_dates) > 0:
        trade_date = future_dates[0]
        signal.loc[trade_date, symbol] = 1

print(f"  Signals: {(signal == 1).sum().sum()}")

# 3. Grid Search
print("\n[3/4] Grid Search 실행...")

HORIZON = 20  # 고정
FEE_RATE = 0.0005  # 0.05%
TILT_SIZES = [0.005, 0.0075, 0.01, 0.0125, 0.015]  # 0.5%p ~ 1.5%p

results = []

for tilt_size in TILT_SIZES:
    print(f"\n  Tilt Size: {tilt_size*100:.2f}%p...")
    
    base_ret, overlay_ret, incr_ret, event_book = backtest_pure_tilt(
        w_base=w_base,
        signal=signal,
        px=px,
        horizon_days=HORIZON,
        tilt_per_event=tilt_size,
        fee_rate=FEE_RATE,
        funding_method='proportional'
    )
    
    # 통계 계산
    def compute_stats(ret):
        mean_ret = ret.mean()
        std_ret = ret.std()
        sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret > 0 else 0
        return sharpe
    
    # Period split
    train_start, train_end = "2016-01-01", "2019-12-31"
    val_start, val_end = "2020-01-01", "2021-12-31"
    test_start, test_end = "2022-01-01", "2025-12-31"
    
    full_sharpe = compute_stats(incr_ret)
    train_sharpe = compute_stats(incr_ret[train_start:train_end])
    val_sharpe = compute_stats(incr_ret[val_start:val_end])
    test_sharpe = compute_stats(incr_ret[test_start:test_end])
    
    # Turnover 추정
    total_events = (signal == 1).sum().sum()
    years = (incr_ret.index[-1] - incr_ret.index[0]).days / 365.25
    annual_events = total_events / years
    estimated_turnover = 2 * annual_events * tilt_size * 100
    
    result = {
        'tilt_size': tilt_size,
        'horizon': HORIZON,
        'fee_rate': FEE_RATE,
        'full_sharpe': full_sharpe,
        'train_sharpe': train_sharpe,
        'val_sharpe': val_sharpe,
        'test_sharpe': test_sharpe,
        'estimated_turnover': estimated_turnover
    }
    
    results.append(result)
    
    print(f"    Full: {full_sharpe:.4f}, Train: {train_sharpe:.4f}, Val: {val_sharpe:.4f}, Test: {test_sharpe:.4f}")

# 4. 결과 분석
print("\n[4/4] 결과 분석...")

df_results = pd.DataFrame(results)
df_results = df_results.sort_values('full_sharpe', ascending=False)

print("\n최선 5개 (Full Sharpe 기준):")
print(df_results.head().to_string(index=False))

# 최선 선택
best = df_results.iloc[0]
print(f"\n최선 파라미터:")
print(f"  Tilt Size: {best['tilt_size']*100:.2f}%p")
print(f"  Horizon: {best['horizon']:.0f} days")
print(f"  Full Sharpe: {best['full_sharpe']:.4f}")
print(f"  Train Sharpe: {best['train_sharpe']:.4f}")
print(f"  Val Sharpe: {best['val_sharpe']:.4f}")
print(f"  Test Sharpe: {best['test_sharpe']:.4f}")
print(f"  Estimated Turnover: {best['estimated_turnover']:.1f}%")

# Train/Val/Test 모두 양수 체크
all_positive = (best['train_sharpe'] > 0 and 
                best['val_sharpe'] > 0 and 
                best['test_sharpe'] > 0)

print(f"\nTrain/Val/Test 모두 양수: {'✅ YES' if all_positive else '❌ NO'}")

# 저장
output_dir = project_root / "results" / "tilt_size_grid"
output_dir.mkdir(parents=True, exist_ok=True)

df_results.to_csv(output_dir / "tilt_size_grid_results.csv", index=False)

with open(output_dir / "best_config.json", 'w') as f:
    json.dump({
        'tilt_size': float(best['tilt_size']),
        'horizon': int(best['horizon']),
        'fee_rate': float(best['fee_rate']),
        'full_sharpe': float(best['full_sharpe']),
        'train_sharpe': float(best['train_sharpe']),
        'val_sharpe': float(best['val_sharpe']),
        'test_sharpe': float(best['test_sharpe']),
        'estimated_turnover': float(best['estimated_turnover']),
        'all_positive': bool(all_positive)
    }, f, indent=2)

print(f"\n결과 저장: {output_dir}")
print("="*80)
