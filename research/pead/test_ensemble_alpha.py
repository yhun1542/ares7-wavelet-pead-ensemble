#!/usr/bin/env python3
"""
PEAD+Buyback 앙상블 알파 검증
Pure Tilt + Ensemble Signal (60% PEAD + 40% Buyback)
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from research.pead.event_book import backtest_pure_tilt

print("="*80)
print("PEAD+Buyback 앙상블 알파 검증")
print("="*80)

# 1. Load data
print("\n[1/5] 데이터 로딩...")
px_long = pd.read_csv(project_root / "data" / "prices.csv")
px_long['timestamp'] = pd.to_datetime(px_long['timestamp'])
px = px_long.pivot(index='timestamp', columns='symbol', values='close')
px = px.ffill().fillna(0)

w_base_long = pd.read_csv(project_root / "data" / "ares7_base_weights.csv", parse_dates=['date'])
w_base = w_base_long.pivot(index='date', columns='symbol', values='weight')
w_base = w_base.fillna(0)

signal_ens = pd.read_csv(project_root / "data" / "signal_ensemble.csv", index_col=0, parse_dates=True)

print(f"  Prices: {px.shape}")
print(f"  Base weights: {w_base.shape}")
print(f"  Ensemble signal: {signal_ens.shape}")

# 2. Align
print("\n[2/5] 데이터 정렬...")
common_dates = px.index.intersection(w_base.index).intersection(signal_ens.index)
common_symbols = sorted(set(px.columns) & set(w_base.columns) & set(signal_ens.columns))

px = px.reindex(index=common_dates, columns=common_symbols)
w_base = w_base.reindex(index=common_dates, columns=common_symbols).fillna(0.0)
signal_ens = signal_ens.reindex(index=common_dates, columns=common_symbols).fillna(0.0)

print(f"  Common dates: {len(common_dates)}")
print(f"  Common symbols: {len(common_symbols)}")

# 3. 파라미터
print("\n[3/5] 파라미터 설정...")
TILT_SIZE = 0.015  # 1.5%p
HORIZON = 30  # 30 days
FEE_RATE = 0.0005  # 0.05%

print(f"  Tilt Size: {TILT_SIZE*100:.2f}%p")
print(f"  Horizon: {HORIZON} days")
print(f"  Fee Rate: {FEE_RATE*100:.2f}%")
print(f"  Ensemble: 60% PEAD + 40% Buyback")

# 4. 백테스트
print("\n[4/5] Pure Tilt 백테스트 실행...")
base_ret, overlay_ret, incr_ret, event_book = backtest_pure_tilt(
    w_base=w_base,
    signal=signal_ens,
    px=px,
    horizon_days=HORIZON,
    tilt_per_event=TILT_SIZE,
    fee_rate=FEE_RATE,
    funding_method='proportional'
)

print(f"  Returns computed: {len(base_ret)} days")

# 5. 성과 분석
print("\n[5/5] 성과 분석...")

def compute_stats(ret):
    mean_ret = ret.mean()
    std_ret = ret.std()
    sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret > 0 else 0
    ann_return = mean_ret * 252
    ann_vol = std_ret * np.sqrt(252)
    
    cum_ret = (1 + ret).cumprod()
    running_max = cum_ret.expanding().max()
    drawdown = (cum_ret - running_max) / running_max
    mdd = drawdown.min()
    
    return {
        'sharpe': sharpe,
        'ann_return': ann_return,
        'ann_vol': ann_vol,
        'mdd': mdd
    }

# Period split
train_start, train_end = "2016-01-01", "2019-12-31"
val_start, val_end = "2020-01-01", "2021-12-31"
test_start, test_end = "2022-01-01", "2025-12-31"

# Base stats
base_all = compute_stats(base_ret)
base_train = compute_stats(base_ret[train_start:train_end])
base_val = compute_stats(base_ret[val_start:val_end])
base_test = compute_stats(base_ret[test_start:test_end])

# Overlay stats
overlay_all = compute_stats(overlay_ret)
overlay_train = compute_stats(overlay_ret[train_start:train_end])
overlay_val = compute_stats(overlay_ret[val_start:val_end])
overlay_test = compute_stats(overlay_ret[test_start:test_end])

# Incremental stats
incr_all = compute_stats(incr_ret)
incr_train = compute_stats(incr_ret[train_start:train_end])
incr_val = compute_stats(incr_ret[val_start:val_end])
incr_test = compute_stats(incr_ret[test_start:test_end])

print("\n" + "="*80)
print("PEAD+Buyback 앙상블 결과")
print("="*80)

print("\n[Base Strategy]")
print(f"  All:   Sharpe {base_all['sharpe']:.4f}, Return {base_all['ann_return']*100:.2f}%, Vol {base_all['ann_vol']*100:.2f}%, MDD {base_all['mdd']*100:.2f}%")
print(f"  Train: Sharpe {base_train['sharpe']:.4f}")
print(f"  Val:   Sharpe {base_val['sharpe']:.4f}")
print(f"  Test:  Sharpe {base_test['sharpe']:.4f}")

print("\n[Overlay Strategy (Base + PEAD + Buyback)]")
print(f"  All:   Sharpe {overlay_all['sharpe']:.4f}, Return {overlay_all['ann_return']*100:.2f}%, Vol {overlay_all['ann_vol']*100:.2f}%, MDD {overlay_all['mdd']*100:.2f}%")
print(f"  Train: Sharpe {overlay_train['sharpe']:.4f}")
print(f"  Val:   Sharpe {overlay_val['sharpe']:.4f}")
print(f"  Test:  Sharpe {overlay_test['sharpe']:.4f}")

print("\n[Incremental Performance (PEAD+Buyback Ensemble)]")
print(f"  All:   Sharpe {incr_all['sharpe']:.4f}, Return {incr_all['ann_return']*100:.2f}%, Vol {incr_all['ann_vol']*100:.2f}%")
print(f"  Train: Sharpe {incr_train['sharpe']:.4f}")
print(f"  Val:   Sharpe {incr_val['sharpe']:.4f}")
print(f"  Test:  Sharpe {incr_test['sharpe']:.4f}")

# Event book 분석
print("\n[Event Book Analysis]")
event_history = event_book.get_event_history_df()
if len(event_history) > 0 and 'status' in event_history.columns:
    opened_events = event_history[event_history['status'] == 'opened']
    closed_events = event_history[event_history['status'] == 'closed']
    print(f"  Total events opened: {len(opened_events)}")
    print(f"  Total events closed: {len(closed_events)}")
    if len(opened_events) > 0:
        print(f"  Average tilt: {opened_events['tilt_amount'].mean()*100:.3f}%p")

# Turnover 추정
total_signals = (signal_ens > 0).sum().sum()
years = (base_ret.index[-1] - base_ret.index[0]).days / 365.25
annual_signals = total_signals / years
estimated_turnover = 2 * annual_signals * TILT_SIZE * 100 / len(common_symbols)  # per ticker
estimated_cost = estimated_turnover * FEE_RATE

print("\n[Turnover & Cost]")
print(f"  Total signals: {total_signals}")
print(f"  Annual signals: {annual_signals:.1f}")
print(f"  Estimated annual turnover: {estimated_turnover:.1f}%")
print(f"  Estimated annual cost: {estimated_cost:.2f}%")

# 평가
print("\n" + "="*80)
print("평가")
print("="*80)

all_positive = (incr_train['sharpe'] > 0 and 
                incr_val['sharpe'] > 0 and 
                incr_test['sharpe'] > 0)

print(f"  Incremental Sharpe > 0: {'✅ YES' if incr_all['sharpe'] > 0 else '❌ NO'} ({incr_all['sharpe']:.4f})")
print(f"  Train/Val/Test 모두 양수: {'✅ YES' if all_positive else '❌ NO'}")
print(f"  Combined Sharpe > Base: {'✅ YES' if overlay_all['sharpe'] > base_all['sharpe'] else '❌ NO'}")
print(f"  Combined Sharpe > 1.0: {'✅ YES' if overlay_all['sharpe'] > 1.0 else '❌ NO'}")

if overlay_all['sharpe'] > 1.0:
    print("\n🎉 목표 달성! Combined Sharpe > 1.0!")
    print(f"   Combined Sharpe: {overlay_all['sharpe']:.4f}")
    print(f"   Incremental Sharpe: {incr_all['sharpe']:.4f}")
elif incr_all['sharpe'] > 0:
    print("\n✅ 앙상블 알파 확인!")
    print(f"   Incremental Sharpe: {incr_all['sharpe']:.4f}")
    print(f"   Combined Sharpe: {overlay_all['sharpe']:.4f} (Base {base_all['sharpe']:.4f})")
else:
    print("\n❌ 앙상블 알파 미확인")
    print(f"   Incremental Sharpe: {incr_all['sharpe']:.4f}")

print("\n" + "="*80)

# 저장
results = {
    'base_all': base_all,
    'overlay_all': overlay_all,
    'incr_all': incr_all,
    'base_train': base_train,
    'base_val': base_val,
    'base_test': base_test,
    'overlay_train': overlay_train,
    'overlay_val': overlay_val,
    'overlay_test': overlay_test,
    'incr_train': incr_train,
    'incr_val': incr_val,
    'incr_test': incr_test,
}

results_df = pd.DataFrame(results).T
results_df.to_csv(project_root / "results" / "ensemble_alpha_results.csv")
print(f"\n결과 저장: results/ensemble_alpha_results.csv")
