#!/usr/bin/env python3
"""
Train/Val/Test 일관성 분석
과적합 원인 파악 및 해결 방안 제시
"""

import pandas as pd
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

project_root = Path(__file__).parent.parent.parent

print("="*80)
print("Train/Val/Test 일관성 분석")
print("="*80)

# 1. Load results
print("\n[1/5] 결과 로딩...")
results_path = project_root / "results" / "pure_tilt" / "pure_tilt_returns.csv"
df = pd.read_csv(results_path, index_col=0, parse_dates=True)

print(f"  Data: {len(df)} days")
print(f"  Columns: {df.columns.tolist()}")

# 2. Period split
print("\n[2/5] Period 분할...")
train_start, train_end = "2016-01-01", "2019-12-31"
val_start, val_end = "2020-01-01", "2021-12-31"
test_start, test_end = "2022-01-01", "2025-12-31"

train = df[train_start:train_end]
val = df[val_start:val_end]
test = df[test_start:test_end]

print(f"  Train: {len(train)} days ({train.index[0]} ~ {train.index[-1]})")
print(f"  Val: {len(val)} days ({val.index[0]} ~ {val.index[-1]})")
print(f"  Test: {len(test)} days ({test.index[0]} ~ {test.index[-1]})")

# 3. 이벤트 분포 분석
print("\n[3/5] 이벤트 분포 분석...")
events = pd.read_csv(project_root / "data" / "pead_event_table.csv", parse_dates=['date'])

train_events = events[(events['date'] >= train_start) & (events['date'] <= train_end)]
val_events = events[(events['date'] >= val_start) & (events['date'] <= val_end)]
test_events = events[(events['date'] >= test_start) & (events['date'] <= test_end)]

print(f"  Train events: {len(train_events)} ({len(train_events)/len(events)*100:.1f}%)")
print(f"  Val events: {len(val_events)} ({len(val_events)/len(events)*100:.1f}%)")
print(f"  Test events: {len(test_events)} ({len(test_events)/len(events)*100:.1f}%)")

# 4. Incremental Return 분석
print("\n[4/5] Incremental Return 상세 분석...")

def analyze_incr_ret(ret, name):
    """Incremental return 상세 분석"""
    mean = ret.mean() * 252
    std = ret.std() * np.sqrt(252)
    sharpe = mean / std if std > 0 else 0
    
    # 양수/음수 비율
    pos_ratio = (ret > 0).sum() / len(ret)
    
    # 누적 수익
    cum_ret = (1 + ret).cumprod() - 1
    
    # 최대/최소
    max_ret = ret.max()
    min_ret = ret.min()
    
    return {
        'period': name,
        'days': len(ret),
        'mean_daily': ret.mean(),
        'std_daily': ret.std(),
        'sharpe': sharpe,
        'ann_return': mean,
        'ann_vol': std,
        'pos_ratio': pos_ratio,
        'max_daily': max_ret,
        'min_daily': min_ret,
        'cum_return': cum_ret.iloc[-1] if len(cum_ret) > 0 else 0
    }

train_stats = analyze_incr_ret(train['incr_ret'], 'Train')
val_stats = analyze_incr_ret(val['incr_ret'], 'Val')
test_stats = analyze_incr_ret(test['incr_ret'], 'Test')

print("\n[Train]")
print(f"  Days: {train_stats['days']}")
print(f"  Sharpe: {train_stats['sharpe']:.4f}")
print(f"  Ann Return: {train_stats['ann_return']*100:.2f}%")
print(f"  Ann Vol: {train_stats['ann_vol']*100:.2f}%")
print(f"  Positive Days: {train_stats['pos_ratio']*100:.1f}%")
print(f"  Cum Return: {train_stats['cum_return']*100:.2f}%")
print(f"  Max Daily: {train_stats['max_daily']*100:.2f}%")
print(f"  Min Daily: {train_stats['min_daily']*100:.2f}%")

print("\n[Val]")
print(f"  Days: {val_stats['days']}")
print(f"  Sharpe: {val_stats['sharpe']:.4f}")
print(f"  Ann Return: {val_stats['ann_return']*100:.2f}%")
print(f"  Ann Vol: {val_stats['ann_vol']*100:.2f}%")
print(f"  Positive Days: {val_stats['pos_ratio']*100:.1f}%")
print(f"  Cum Return: {val_stats['cum_return']*100:.2f}%")
print(f"  Max Daily: {val_stats['max_daily']*100:.2f}%")
print(f"  Min Daily: {val_stats['min_daily']*100:.2f}%")

print("\n[Test]")
print(f"  Days: {test_stats['days']}")
print(f"  Sharpe: {test_stats['sharpe']:.4f}")
print(f"  Ann Return: {test_stats['ann_return']*100:.2f}%")
print(f"  Ann Vol: {test_stats['ann_vol']*100:.2f}%")
print(f"  Positive Days: {test_stats['pos_ratio']*100:.1f}%")
print(f"  Cum Return: {test_stats['cum_return']*100:.2f}%")
print(f"  Max Daily: {test_stats['max_daily']*100:.2f}%")
print(f"  Min Daily: {test_stats['min_daily']*100:.2f}%")

# 5. EPS Surprise 분포 분석
print("\n[5/5] EPS Surprise 분포 분석...")

train_surprise = train_events['surprise'].describe()
val_surprise = val_events['surprise'].describe()
test_surprise = test_events['surprise'].describe()

print("\n[Train Surprise]")
print(train_surprise)

print("\n[Val Surprise]")
print(val_surprise)

print("\n[Test Surprise]")
print(test_surprise)

# 6. 결론 및 권장사항
print("\n" + "="*80)
print("결론 및 권장사항")
print("="*80)

# 이벤트 불균형 체크
event_imbalance = abs(len(test_events) - len(train_events)) / len(events) > 0.2
print(f"\n1. 이벤트 분포 불균형: {'⚠️ YES' if event_imbalance else '✅ NO'}")
if event_imbalance:
    print("   → Test에 이벤트가 집중되어 있음")
    print("   → 해결: Period 재분할 또는 이벤트 샘플링")

# Surprise 분포 차이 체크
surprise_diff = abs(test_surprise['mean'] - train_surprise['mean']) / train_surprise['std']
print(f"\n2. Surprise 분포 차이: {surprise_diff:.2f} std")
if surprise_diff > 1.0:
    print("   ⚠️ Train과 Test의 Surprise 분포가 크게 다름")
    print("   → 해결: Standardized Surprise 사용")
else:
    print("   ✅ Train과 Test의 Surprise 분포 유사")

# Positive ratio 차이 체크
pos_ratio_diff = abs(test_stats['pos_ratio'] - train_stats['pos_ratio'])
print(f"\n3. Positive Days 비율 차이: {pos_ratio_diff*100:.1f}%p")
if pos_ratio_diff > 0.1:
    print("   ⚠️ Train과 Test의 수익 패턴이 다름")
    print("   → 해결: 이벤트 정의 개선 또는 Base Strategy 변경")
else:
    print("   ✅ Train과 Test의 수익 패턴 유사")

# 최종 권장사항
print("\n" + "="*80)
print("최종 권장사항")
print("="*80)

if event_imbalance:
    print("\n✅ Priority 1: Period 재분할")
    print("   - 현재: 2016-2019 (Train), 2020-2021 (Val), 2022-2025 (Test)")
    print("   - 제안: 2016-2020 (Train), 2021-2022 (Val), 2023-2025 (Test)")
    print("   - 효과: 이벤트 분포 균형")

if surprise_diff > 1.0:
    print("\n✅ Priority 2: Standardized Surprise")
    print("   - 현재: Surprise = EPS - EPS_prev")
    print("   - 제안: Surprise = (EPS - EPS_prev) / StdDev(Surprise)")
    print("   - 효과: 시기별 일관성 향상")

print("\n✅ Priority 3: Positive Surprise Only")
print("   - 현재: 상위 10% (양수+음수 혼재)")
print("   - 제안: 양수 중 상위 10%")
print("   - 효과: PEAD 효과 강화")

print("\n" + "="*80)
