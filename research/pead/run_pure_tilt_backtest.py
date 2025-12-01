#!/usr/bin/env python3
"""
Pure Tilt Overlay v2 백테스트 실행

Budget Carve-out 모델과 비교하여 Turnover 감소 효과 검증
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from research.pead.event_book import EventBook, backtest_pure_tilt
from research.pead.overlay_engine import compute_portfolio_returns
# 경로 직접 지정
PRICES_FILE = project_root / "data" / "prices.csv"
BASE_WEIGHTS_FILE = project_root / "data" / "ares7_base_weights.csv"
EVENT_TABLE_FILE = project_root / "data" / "pead_event_table_positive.csv"

print("="*80)
print("Pure Tilt Overlay v2 백테스트")
print("="*80)

# 1. Load data
print("\n[1/6] 데이터 로딩...")

# Prices는 long format이므로 wide format으로 변환 (close 가격만 사용)
px_long = pd.read_csv(PRICES_FILE)
px_long['timestamp'] = pd.to_datetime(px_long['timestamp'])
px = px_long.pivot(index='timestamp', columns='symbol', values='close')
px = px.fillna(method='ffill').fillna(0)

# Base weights는 long format이므로 wide format으로 변환
w_base_long = pd.read_csv(BASE_WEIGHTS_FILE, parse_dates=['date'])
w_base = w_base_long.pivot(index='date', columns='symbol', values='weight')
w_base = w_base.fillna(0)

print(f"  Prices: {px.shape}")
print(f"  Prices date range: {px.index.min()} ~ {px.index.max()}")
print(f"  Base weights: {w_base.shape}")
print(f"  Base weights date range: {w_base.index.min()} ~ {w_base.index.max()}")

# 2. Load event table
print("\n[2/6] 이벤트 테이블 로딩...")
events = pd.read_csv(EVENT_TABLE_FILE, parse_dates=['date'])
print(f"  Events: {len(events)} rows")
print(f"  Date range: {events['date'].min()} ~ {events['date'].max()}")

# 3. Create signal DataFrame
print("\n[3/6] 시그널 생성...")
signal = pd.DataFrame(0, index=px.index, columns=px.columns)

# 날짜 매칭 개선: 이벤트 날짜를 가장 가까운 거래일로 매칭
matched_events = 0
for _, row in events.iterrows():
    event_date = row['date']
    symbol = row['symbol']
    
    if symbol not in signal.columns:
        continue
    
    # 이벤트 날짜 이후 가장 가까운 거래일 찾기
    future_dates = px.index[px.index >= event_date]
    if len(future_dates) > 0:
        trade_date = future_dates[0]
        signal.loc[trade_date, symbol] = 1
        matched_events += 1

pos_events = (signal == 1).sum().sum()
print(f"  Total events: {len(events)}")
print(f"  Matched events: {matched_events}")
print(f"  Positive signals: {pos_events}")
print(f"  Match rate: {matched_events/len(events)*100:.1f}%")

# 4. 파라미터 설정
print("\n[4/6] 파라미터 설정...")

# Grid Search 최선 결과 사용
BUDGET = 0.10  # 10%
HORIZON = 20   # 20 days
FEE_RATE = 0.0005  # 0.05%

# Pure Tilt 파라미터
# Budget 10%를 이벤트당 tilt로 변환
# 가정: 평균 10개 이벤트 동시 활성 → 이벤트당 1%p tilt
TILT_PER_EVENT = 0.01  # 1%p per event

print(f"  Horizon: {HORIZON} days")
print(f"  Tilt per event: {TILT_PER_EVENT*100:.2f}%p")
print(f"  Fee rate: {FEE_RATE*100:.2f}%")

# 5. Pure Tilt 백테스트
print("\n[5/6] Pure Tilt 백테스트 실행...")
base_ret, overlay_ret, incr_ret, event_book = backtest_pure_tilt(
    w_base=w_base,
    signal=signal,
    px=px,
    horizon_days=HORIZON,
    tilt_per_event=TILT_PER_EVENT,
    fee_rate=FEE_RATE,
    funding_method='proportional'
)

print(f"  Returns computed: {len(base_ret)} days")

# 6. 성과 분석
print("\n[6/6] 성과 분석...")

# Split periods
train_start, train_end = "2016-01-01", "2019-12-31"
val_start, val_end = "2020-01-01", "2021-12-31"
test_start, test_end = "2022-01-01", "2025-12-31"

def compute_stats(ret):
    """수익률 통계 계산"""
    mean_ret = ret.mean()
    std_ret = ret.std()
    sharpe = mean_ret / std_ret * np.sqrt(252) if std_ret > 0 else 0
    ann_return = mean_ret * 252
    ann_vol = std_ret * np.sqrt(252)
    
    # MDD 계산
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

def analyze_period(ret, name):
    stats = compute_stats(ret)
    return {
        'period': name,
        'sharpe': stats['sharpe'],
        'ann_return': stats['ann_return'],
        'ann_vol': stats['ann_vol'],
        'mdd': stats['mdd']
    }

# Base stats
base_all = analyze_period(base_ret, 'All')
base_train = analyze_period(base_ret[train_start:train_end], 'Train')
base_val = analyze_period(base_ret[val_start:val_end], 'Val')
base_test = analyze_period(base_ret[test_start:test_end], 'Test')

# Overlay stats
overlay_all = analyze_period(overlay_ret, 'All')
overlay_train = analyze_period(overlay_ret[train_start:train_end], 'Train')
overlay_val = analyze_period(overlay_ret[val_start:val_end], 'Val')
overlay_test = analyze_period(overlay_ret[test_start:test_end], 'Test')

# Incremental stats
incr_all = analyze_period(incr_ret, 'All')
incr_train = analyze_period(incr_ret[train_start:train_end], 'Train')
incr_val = analyze_period(incr_ret[val_start:val_end], 'Val')
incr_test = analyze_period(incr_ret[test_start:test_end], 'Test')

# Print results
print("\n" + "="*80)
print("결과 요약")
print("="*80)

print("\n[Base Strategy]")
print(f"  All:   Sharpe {base_all['sharpe']:.4f}, Return {base_all['ann_return']*100:.2f}%, Vol {base_all['ann_vol']*100:.2f}%, MDD {base_all['mdd']*100:.2f}%")
print(f"  Train: Sharpe {base_train['sharpe']:.4f}")
print(f"  Val:   Sharpe {base_val['sharpe']:.4f}")
print(f"  Test:  Sharpe {base_test['sharpe']:.4f}")

print("\n[Overlay Strategy]")
print(f"  All:   Sharpe {overlay_all['sharpe']:.4f}, Return {overlay_all['ann_return']*100:.2f}%, Vol {overlay_all['ann_vol']*100:.2f}%, MDD {overlay_all['mdd']*100:.2f}%")
print(f"  Train: Sharpe {overlay_train['sharpe']:.4f}")
print(f"  Val:   Sharpe {overlay_val['sharpe']:.4f}")
print(f"  Test:  Sharpe {overlay_test['sharpe']:.4f}")

print("\n[Incremental Performance]")
print(f"  All:   Sharpe {incr_all['sharpe']:.4f}, Return {incr_all['ann_return']*100:.2f}%, Vol {incr_all['ann_vol']*100:.2f}%")
print(f"  Train: Sharpe {incr_train['sharpe']:.4f}")
print(f"  Val:   Sharpe {incr_val['sharpe']:.4f}")
print(f"  Test:  Sharpe {incr_test['sharpe']:.4f}")

# Event book 분석
print("\n[Event Book Analysis]")
event_history = event_book.get_event_history_df()
if len(event_history) > 0:
    print(f"  Total events in history: {len(event_history)}")
    if 'status' in event_history.columns:
        opened_events = event_history[event_history['status'] == 'opened']
        closed_events = event_history[event_history['status'] == 'closed']
        print(f"  Total events opened: {len(opened_events)}")
        print(f"  Total events closed: {len(closed_events)}")
        if len(opened_events) > 0:
            print(f"  Average tilt: {opened_events['tilt_amount'].mean()*100:.3f}%p")
    else:
        print(f"  Event history columns: {event_history.columns.tolist()}")
else:
    print("  No events in history")

# Turnover 추정
print("\n[Turnover Estimation]")
# Pure Tilt: 이벤트 오픈/클로즈 때만 매매
# Turnover ≈ 2 × (total events × tilt_per_event)
if len(event_history) > 0 and 'status' in event_history.columns:
    total_events = len(event_history[event_history['status'] == 'opened'])
else:
    # Signal에서 직접 계산
    total_events = (signal == 1).sum().sum()

years = (base_ret.index[-1] - base_ret.index[0]).days / 365.25
annual_events = total_events / years if years > 0 else 0
estimated_turnover = 2 * annual_events * TILT_PER_EVENT * 100
print(f"  Total events: {total_events}")
print(f"  Annual events: {annual_events:.1f}")
print(f"  Estimated annual turnover: {estimated_turnover:.1f}%")
print(f"  Estimated annual cost: {estimated_turnover * FEE_RATE:.2f}%")

# 비교: Budget Carve-out 모델
print("\n[Comparison with Budget Carve-out]")
print("  Budget Carve-out (from Grid Search):")
print(f"    Annual turnover: ~1,246%")
print(f"    Annual cost: ~2.5%")
print(f"    Full Incr Sharpe: +0.010")
print("\n  Pure Tilt:")
print(f"    Annual turnover: ~{estimated_turnover:.0f}% (예상)")
print(f"    Annual cost: ~{estimated_turnover * FEE_RATE:.2f}% (예상)")
print(f"    Full Incr Sharpe: {incr_all['sharpe']:.4f}")
print(f"\n  Turnover reduction: {(1 - estimated_turnover/1246)*100:.1f}%")
print(f"  Cost reduction: {(1 - (estimated_turnover * FEE_RATE)/2.5)*100:.1f}%")

# 성공 여부 판단
print("\n" + "="*80)
print("성공 기준 평가")
print("="*80)

success_criteria = {
    'Turnover ≤ 400%': estimated_turnover <= 400,
    'Net Incr Sharpe ≥ 0': incr_all['sharpe'] >= 0,
    'Train/Val/Test 모두 양수': (
        incr_train['sharpe'] > 0 and 
        incr_val['sharpe'] > 0 and 
        incr_test['sharpe'] > 0
    )
}

for criterion, passed in success_criteria.items():
    status = "✅ PASS" if passed else "❌ FAIL"
    print(f"  {criterion}: {status}")

all_passed = all(success_criteria.values())
print(f"\n종합 평가: {'✅ SUCCESS' if all_passed else '⚠️ PARTIAL SUCCESS'}")

# Save results
output_dir = project_root / "results" / "pure_tilt"
output_dir.mkdir(parents=True, exist_ok=True)

results_df = pd.DataFrame({
    'base_ret': base_ret,
    'overlay_ret': overlay_ret,
    'incr_ret': incr_ret
})
results_df.to_csv(output_dir / "pure_tilt_returns.csv")

summary = {
    'config': {
        'horizon': HORIZON,
        'tilt_per_event': TILT_PER_EVENT,
        'fee_rate': FEE_RATE
    },
    'base': {
        'all': base_all,
        'train': base_train,
        'val': base_val,
        'test': base_test
    },
    'overlay': {
        'all': overlay_all,
        'train': overlay_train,
        'val': overlay_val,
        'test': overlay_test
    },
    'incremental': {
        'all': incr_all,
        'train': incr_train,
        'val': incr_val,
        'test': incr_test
    },
    'turnover': {
        'total_events': int(total_events),
        'annual_events': float(annual_events),
        'estimated_annual_turnover_pct': float(estimated_turnover),
        'estimated_annual_cost_pct': float(estimated_turnover * FEE_RATE)
    },
    'success_criteria': success_criteria,
    'overall_success': all_passed
}

import json
with open(output_dir / "pure_tilt_summary.json", 'w') as f:
    json.dump(summary, f, indent=2, default=str)

print(f"\n결과 저장: {output_dir}")
print("="*80)
