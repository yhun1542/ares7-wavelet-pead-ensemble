#!/usr/bin/env python3
"""
이벤트 기반 앙상블 테스트
PEAD 이벤트 + Buyback 이벤트 병합 → Pure Tilt
"""

import sys
import pandas as pd
import numpy as np
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from research.pead.event_book import EventBook

print("="*80)
print("이벤트 기반 앙상블 테스트 (PEAD + Buyback)")
print("="*80)

# 1. Load data
print("\n[1/6] 데이터 로딩...")
px_long = pd.read_csv(project_root / "data" / "prices.csv")
px_long['timestamp'] = pd.to_datetime(px_long['timestamp'])
px = px_long.pivot(index='timestamp', columns='symbol', values='close')
px = px.ffill().fillna(0)

w_base_long = pd.read_csv(project_root / "data" / "ares7_base_weights.csv", parse_dates=['date'])
w_base = w_base_long.pivot(index='date', columns='symbol', values='weight')
w_base = w_base.fillna(0)

# PEAD events
events_pead = pd.read_csv(project_root / "data" / "pead_event_table_positive.csv", parse_dates=['date'])
events_pead = events_pead.rename(columns={'date': 'event_date', 'symbol': 'ticker'})
events_pead['source'] = 'PEAD'

# Buyback events
events_bb = pd.read_csv(project_root / "data" / "buyback_events.csv", parse_dates=['event_date'])
events_bb['source'] = 'Buyback'

print(f"  Prices: {px.shape}")
print(f"  Base weights: {w_base.shape}")
print(f"  PEAD events: {len(events_pead)}")
print(f"  Buyback events: {len(events_bb)}")

# 2. Filter events (상위 10%)
print("\n[2/6] 이벤트 필터링...")
pead_top = events_pead[events_pead['surprise_rank'] >= 0.9].copy()
bb_top = events_bb[events_bb['signal_rank'] >= 0.9].copy()

print(f"  PEAD top 10%: {len(pead_top)}")
print(f"  Buyback top 10%: {len(bb_top)}")

# 3. Merge events
print("\n[3/6] 이벤트 병합...")

# PEAD events: ticker, event_date, surprise_rank
pead_events = pead_top[['ticker', 'event_date', 'surprise_rank']].copy()
pead_events['rank'] = pead_events['surprise_rank']
pead_events['source'] = 'PEAD'

# Buyback events: ticker, event_date, signal_rank
bb_events = bb_top[['ticker', 'event_date', 'signal_rank']].copy()
bb_events['rank'] = bb_events['signal_rank']
bb_events['source'] = 'Buyback'

# Combine
all_events = pd.concat([
    pead_events[['ticker', 'event_date', 'rank', 'source']],
    bb_events[['ticker', 'event_date', 'rank', 'source']]
], ignore_index=True)

all_events = all_events.sort_values(['event_date', 'ticker'])
print(f"  Total events: {len(all_events)}")
print(f"  PEAD: {(all_events['source'] == 'PEAD').sum()}")
print(f"  Buyback: {(all_events['source'] == 'Buyback').sum()}")

# 4. Align
print("\n[4/6] 데이터 정렬...")
common_dates = px.index.intersection(w_base.index)
common_symbols = sorted(set(px.columns) & set(w_base.columns))

px = px.reindex(index=common_dates, columns=common_symbols)
w_base = w_base.reindex(index=common_dates, columns=common_symbols).fillna(0.0)

print(f"  Common dates: {len(common_dates)}")
print(f"  Common symbols: {len(common_symbols)}")

# 5. 파라미터
print("\n[5/6] 파라미터 설정...")
TILT_SIZE = 0.015  # 1.5%p
HORIZON = 30  # 30 days
FEE_RATE = 0.0005  # 0.05%
MIN_RANK = 0.8

print(f"  Tilt Size: {TILT_SIZE*100:.2f}%p")
print(f"  Horizon: {HORIZON} days")
print(f"  Fee Rate: {FEE_RATE*100:.2f}%")
print(f"  Min Rank: {MIN_RANK}")

# 6. 백테스트
print("\n[6/6] Pure Tilt 백테스트 실행...")

event_book = EventBook()
w_overlay = w_base.copy()
base_ret_list = []
overlay_ret_list = []

dates = sorted(common_dates)

for i, date in enumerate(dates):
    if i == 0:
        continue
    
    prev_date = dates[i-1]
    
    # 이벤트 처리
    day_events = all_events[all_events['event_date'] == date]
    
    for _, event in day_events.iterrows():
        ticker = event['ticker']
        rank = event['rank']
        
        if ticker not in common_symbols:
            continue
        
        # Strength 계산 (rank는 이미 0.9~1.0 범위)
        # MIN_RANK 필터를 제거하고 rank를 직접 사용
        strength = rank
        
        tilt_amount = TILT_SIZE * strength
        
        # 이벤트 오픈
        event_book.add_event(
            symbol=ticker,
            open_date=date,
            horizon_days=HORIZON,
            tilt_amount=tilt_amount
        )
    
    # 이벤트 만료 체크
    event_book.close_expired_events(date)
    
    # 현재 active tilts
    active_tilts = event_book.get_active_tilts(date)
    
    # Overlay weights 계산
    w_day = w_base.loc[date].copy()
    
    for ticker, tilt in active_tilts.items():
        if ticker in w_day.index:
            w_day[ticker] += tilt
    
    # Funding (proportional)
    total_tilt = sum(active_tilts.values())
    if total_tilt > 0:
        for ticker in w_day.index:
            if ticker not in active_tilts:
                w_day[ticker] -= total_tilt * w_base.loc[date, ticker] / (1 - total_tilt + 1e-10)
    
    # Normalize
    w_day = w_day.clip(0, None)
    w_sum = w_day.sum()
    if w_sum > 0:
        w_day /= w_sum
    
    w_overlay.loc[date] = w_day
    
    # Returns
    px_ret = (px.loc[date] - px.loc[prev_date]) / px.loc[prev_date]
    px_ret = px_ret.fillna(0)
    
    base_ret = (w_base.loc[prev_date] * px_ret).sum()
    overlay_ret_gross = (w_day * px_ret).sum()
    
    # Turnover & cost
    if i > 1:
        prev_prev_date = dates[i-2]
        turnover = (w_overlay.loc[date] - w_overlay.loc[prev_date]).abs().sum()
        cost = turnover * FEE_RATE
    else:
        cost = 0
    
    overlay_ret_net = overlay_ret_gross - cost
    
    base_ret_list.append(base_ret)
    overlay_ret_list.append(overlay_ret_net)

base_ret = pd.Series(base_ret_list, index=dates[1:])
overlay_ret = pd.Series(overlay_ret_list, index=dates[1:])
incr_ret = overlay_ret - base_ret

print(f"  Returns computed: {len(base_ret)} days")

# 7. 성과 분석
print("\n성과 분석...")

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

# Stats
base_all = compute_stats(base_ret)
overlay_all = compute_stats(overlay_ret)
incr_all = compute_stats(incr_ret)

incr_train = compute_stats(incr_ret[train_start:train_end])
incr_val = compute_stats(incr_ret[val_start:val_end])
incr_test = compute_stats(incr_ret[test_start:test_end])

print("\n" + "="*80)
print("이벤트 기반 앙상블 결과 (PEAD + Buyback)")
print("="*80)

print("\n[Base Strategy]")
print(f"  Sharpe: {base_all['sharpe']:.4f}")

print("\n[Overlay Strategy (Base + PEAD + Buyback)]")
print(f"  Sharpe: {overlay_all['sharpe']:.4f}")

print("\n[Incremental Performance (PEAD+Buyback)]")
print(f"  All:   Sharpe {incr_all['sharpe']:.4f}, Return {incr_all['ann_return']*100:.2f}%, Vol {incr_all['ann_vol']*100:.2f}%")
print(f"  Train: Sharpe {incr_train['sharpe']:.4f}")
print(f"  Val:   Sharpe {incr_val['sharpe']:.4f}")
print(f"  Test:  Sharpe {incr_test['sharpe']:.4f}")

# Event book
event_history = event_book.get_event_history_df()
if len(event_history) > 0:
    opened = event_history[event_history['status'] == 'opened']
    closed = event_history[event_history['status'] == 'closed']
    print(f"\n[Event Book]")
    print(f"  Events opened: {len(opened)}")
    print(f"  Events closed: {len(closed)}")
    if len(opened) > 0:
        print(f"  Average tilt: {opened['tilt_amount'].mean()*100:.3f}%p")

# 평가
print("\n" + "="*80)
print("평가")
print("="*80)

all_positive = (incr_train['sharpe'] > 0 and 
                incr_val['sharpe'] > 0 and 
                incr_test['sharpe'] > 0)

print(f"  Incremental Sharpe > 0: {'✅ YES' if incr_all['sharpe'] > 0 else '❌ NO'} ({incr_all['sharpe']:.4f})")
print(f"  Train/Val/Test 모두 양수: {'✅ YES' if all_positive else '❌ NO'}")
print(f"  Combined Sharpe > 1.0: {'✅ YES' if overlay_all['sharpe'] > 1.0 else '❌ NO'}")

if overlay_all['sharpe'] > 1.0:
    print("\n🎉 목표 달성! Combined Sharpe > 1.0!")
    print(f"   Combined Sharpe: {overlay_all['sharpe']:.4f}")
elif incr_all['sharpe'] > 0:
    print("\n✅ 앙상블 알파 확인!")
    print(f"   Incremental Sharpe: {incr_all['sharpe']:.4f}")
    print(f"   Combined Sharpe: {overlay_all['sharpe']:.4f}")

print("\n" + "="*80)
