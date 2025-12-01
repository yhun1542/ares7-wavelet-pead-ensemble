#!/usr/bin/env python3
"""
Positive Surprise Only 이벤트 테이블 생성
양수 EPS Surprise 중 상위 10%만 선택
"""

import pandas as pd
import numpy as np
from pathlib import Path

project_root = Path(__file__).parent.parent.parent

print("="*80)
print("Positive Surprise Only 이벤트 테이블 생성")
print("="*80)

# 1. Load SF1 EPS data
print("\n[1/5] SF1 EPS 데이터 로딩...")
sf1_path = project_root / "data" / "sf1_eps.csv"
df = pd.read_csv(sf1_path)

print(f"  원본 데이터: {len(df)} rows")

# 2. 데이터 전처리
print("\n[2/5] 데이터 전처리...")
df['datekey'] = pd.to_datetime(df['datekey'])
if 'ticker' in df.columns:
    df['symbol'] = df['ticker']

df = df.dropna(subset=['eps'])
df = df[(df['datekey'] >= '2016-01-01') & (df['datekey'] <= '2025-12-31')]

print(f"  필터링 후: {len(df)} rows")

# 3. EPS Surprise 계산
print("\n[3/5] EPS Surprise 계산...")
df = df.sort_values(['symbol', 'datekey'])
df['eps_prev'] = df.groupby('symbol')['eps'].shift(1)
df['surprise'] = df['eps'] - df['eps_prev']
df = df.dropna(subset=['surprise'])

print(f"  Surprise 계산 후: {len(df)} rows")

# 4. Positive Surprise만 필터링
print("\n[4/5] Positive Surprise 필터링...")
df_pos = df[df['surprise'] > 0].copy()

print(f"  Positive Surprise: {len(df_pos)} rows ({len(df_pos)/len(df)*100:.1f}%)")
print(f"  Negative Surprise: {len(df) - len(df_pos)} rows ({(len(df)-len(df_pos))/len(df)*100:.1f}%)")

# 5. 각 날짜별 상위 10% 선택
print("\n[5/5] 상위 10% 선택...")

# Cross-sectional Rank (Positive 중에서만)
df_pos['surprise_rank'] = df_pos.groupby('datekey')['surprise'].rank(pct=True)

# 상위 10%
POS_THRESHOLD = 0.90
df_top = df_pos[df_pos['surprise_rank'] >= POS_THRESHOLD].copy()

print(f"  상위 10% 이벤트: {len(df_top)} rows")

# 6. 이벤트 테이블 생성
events = df_top[['datekey', 'symbol', 'eps', 'eps_prev', 'surprise', 'surprise_rank']].copy()
events = events.rename(columns={'datekey': 'date'})
events = events.sort_values('date').reset_index(drop=True)

print(f"\n최종 이벤트 테이블: {len(events)} rows")
print(f"날짜 범위: {events['date'].min()} ~ {events['date'].max()}")
print(f"종목 수: {events['symbol'].nunique()}")

# 7. 비교
print("\n기존 vs 개선:")
old_events = pd.read_csv(project_root / "data" / "pead_event_table.csv")
print(f"  기존 (상위 10% 전체): {len(old_events)} events")
print(f"  개선 (Positive 중 상위 10%): {len(events)} events")
print(f"  감소: {len(old_events) - len(events)} events ({(len(old_events)-len(events))/len(old_events)*100:.1f}%)")

# 8. 저장
output_path = project_root / "data" / "pead_event_table_positive.csv"
events.to_csv(output_path, index=False)
print(f"\n저장 완료: {output_path}")

# 9. 통계
print("\n통계:")
print(f"  평균 Surprise: {events['surprise'].mean():.4f}")
print(f"  Surprise 표준편차: {events['surprise'].std():.4f}")
print(f"  최소 Surprise: {events['surprise'].min():.4f}")
print(f"  최대 Surprise: {events['surprise'].max():.4f}")
print(f"  평균 Rank: {events['surprise_rank'].mean():.4f}")

# 10. Period별 분포
print("\nPeriod별 분포:")
train_events = events[(events['date'] >= '2016-01-01') & (events['date'] <= '2019-12-31')]
val_events = events[(events['date'] >= '2020-01-01') & (events['date'] <= '2021-12-31')]
test_events = events[(events['date'] >= '2022-01-01') & (events['date'] <= '2025-12-31')]

print(f"  Train: {len(train_events)} ({len(train_events)/len(events)*100:.1f}%)")
print(f"  Val: {len(val_events)} ({len(val_events)/len(events)*100:.1f}%)")
print(f"  Test: {len(test_events)} ({len(test_events)/len(events)*100:.1f}%)")

print("\n" + "="*80)
print("완료!")
print("="*80)
