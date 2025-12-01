#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_vix_futures_yfinance.py

yfinance를 사용하여 VIX 현물 + VIX 선물 데이터 다운로드
- VIX: ^VIX (현물)
- F1: VXX (VIX 단기 선물 ETN)
- F2: ^VIX9D (VIX 9일 선물 지수)
"""

import pandas as pd
import yfinance as yf
from datetime import datetime

def main():
    # 날짜 범위 설정
    start_date = "2015-11-23"
    end_date = "2025-11-22"
    
    print("VIX 데이터 다운로드 중 (yfinance)...\n")
    
    # VIX 현물
    print("1. VIX 현물 (^VIX) 다운로드...")
    vix = yf.download("^VIX", start=start_date, end=end_date, progress=False)
    vix = vix[['Close']].rename(columns={'Close': 'VIX'})
    print(f"   ✅ {len(vix)} 레코드")
    
    # VXX (VIX 단기 선물 ETN) - F1으로 사용
    print("\n2. VXX (VIX 단기 선물 ETN) 다운로드...")
    vxx = yf.download("VXX", start=start_date, end=end_date, progress=False)
    vxx = vxx[['Close']].rename(columns={'Close': 'F1'})
    print(f"   ✅ {len(vxx)} 레코드")
    
    # ^VIX9D (VIX 9일 선물) - F2로 사용
    print("\n3. ^VIX9D (VIX 9일 선물) 다운로드...")
    vix9d = yf.download("^VIX9D", start=start_date, end=end_date, progress=False)
    vix9d = vix9d[['Close']].rename(columns={'Close': 'F2'})
    print(f"   ✅ {len(vix9d)} 레코드")
    
    # 데이터 병합
    print("\n4. 데이터 병합 중...")
    df = pd.concat([vix, vxx, vix9d], axis=1)
    df = df.dropna()  # 모든 데이터가 있는 날짜만 유지
    
    # 인덱스를 date 컬럼으로 변환
    df = df.reset_index()
    df = df.rename(columns={'Date': 'date'})
    df['date'] = pd.to_datetime(df['date']).dt.date
    
    # 저장
    output_path = "data/vix_futures.csv"
    df.to_csv(output_path, index=False)
    
    print(f"\n✅ VIX 선물 데이터 저장 완료: {output_path}")
    print(f"   총 {len(df)} 레코드")
    print(f"   기간: {df['date'].min()} ~ {df['date'].max()}")
    print(f"\n데이터 구성:")
    print(f"  - VIX: CBOE Volatility Index (현물)")
    print(f"  - F1: VXX (VIX 단기 선물 ETN, 실제 거래 가능)")
    print(f"  - F2: ^VIX9D (VIX 9일 선물 지수)")
    print(f"\n샘플 데이터:")
    print(df.head(10))
    
    # Contango/Backwardation 확인
    df_check = df.copy()
    df_check['contango'] = df_check['F2'] / df_check['F1'] - 1.0
    backwardation_pct = (df_check['contango'] < 0).sum() / len(df_check) * 100
    print(f"\n통계:")
    print(f"  - Backwardation 비율: {backwardation_pct:.1f}%")
    print(f"  - Contango 비율: {100-backwardation_pct:.1f}%")

if __name__ == "__main__":
    main()
