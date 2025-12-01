#!/usr/bin/env python3
"""
간단한 PEAD 이벤트 테이블 생성
SF1 EPS 데이터에서 상위/하위 서프라이즈 이벤트 추출
"""

import pandas as pd
import numpy as np
from pathlib import Path

project_root = Path(__file__).parent.parent.parent

print("="*80)
print("PEAD 이벤트 테이블 생성")
print("="*80)

# 1. Load SF1 EPS data
print("\n[1/4] SF1 EPS 데이터 로딩...")
sf1_path = project_root / "data" / "sf1_eps.csv"
df = pd.read_csv(sf1_path)

print(f"  원본 데이터: {len(df)} rows")
print(f"  컬럼: {df.columns.tolist()}")

# 2. 데이터 전처리
print("\n[2/4] 데이터 전처리...")

# datekey를 datetime으로 변환
df['datekey'] = pd.to_datetime(df['datekey'])

# ticker를 symbol로 변경
if 'ticker' in df.columns:
    df['symbol'] = df['ticker']

# 필수 컬럼 확인
required_cols = ['symbol', 'datekey', 'eps']
missing = [col for col in required_cols if col not in df.columns]
if missing:
    raise ValueError(f"Missing columns: {missing}")

# NaN 제거
df = df.dropna(subset=['eps'])

# 날짜 범위 필터 (2016-2025)
df = df[(df['datekey'] >= '2016-01-01') & (df['datekey'] <= '2025-12-31')]

print(f"  필터링 후: {len(df)} rows")
print(f"  날짜 범위: {df['datekey'].min()} ~ {df['datekey'].max()}")
print(f"  종목 수: {df['symbol'].nunique()}")

# 3. EPS Surprise 계산
print("\n[3/4] EPS Surprise 계산...")

# 각 종목별로 이전 EPS와 비교
df = df.sort_values(['symbol', 'datekey'])

# 이전 EPS (lag)
df['eps_prev'] = df.groupby('symbol')['eps'].shift(1)

# Surprise = eps - eps_prev
df['surprise'] = df['eps'] - df['eps_prev']

# NaN 제거 (첫 번째 관측치)
df = df.dropna(subset=['surprise'])

print(f"  Surprise 계산 후: {len(df)} rows")

# 4. 각 날짜별 Cross-sectional Rank
print("\n[4/4] Cross-sectional Rank 계산...")

# 각 날짜별로 surprise를 0-1 범위로 정규화
df['surprise_rank'] = df.groupby('datekey')['surprise'].rank(pct=True)

# 상위 10% (pos_top) 이벤트만 선택
POS_THRESHOLD = 0.90
df_pos = df[df['surprise_rank'] >= POS_THRESHOLD].copy()

print(f"  상위 10% 이벤트: {len(df_pos)} rows")

# 5. 이벤트 테이블 생성
events = df_pos[['datekey', 'symbol', 'eps', 'eps_prev', 'surprise', 'surprise_rank']].copy()
events = events.rename(columns={'datekey': 'date'})

# 날짜 정렬
events = events.sort_values('date').reset_index(drop=True)

print(f"\n최종 이벤트 테이블: {len(events)} rows")
print(f"날짜 범위: {events['date'].min()} ~ {events['date'].max()}")
print(f"종목 수: {events['symbol'].nunique()}")

# 6. 저장
output_path = project_root / "data" / "pead_event_table.csv"
events.to_csv(output_path, index=False)
print(f"\n저장 완료: {output_path}")

# 7. 샘플 출력
print("\n샘플 (처음 10개):")
print(events.head(10).to_string())

print("\n통계:")
print(f"  평균 Surprise: {events['surprise'].mean():.4f}")
print(f"  Surprise 표준편차: {events['surprise'].std():.4f}")
print(f"  평균 Rank: {events['surprise_rank'].mean():.4f}")

print("\n" + "="*80)
print("완료!")
print("="*80)
