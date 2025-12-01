#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_vix_yahoo.py

Yahoo Finance를 사용하여 VIX 데이터 다운로드
"""

import pandas as pd
import yfinance as yf
from datetime import datetime

def main():
    # 날짜 범위 설정
    start_date = "2015-11-23"
    end_date = "2025-11-22"  # Yahoo는 end_date를 포함하지 않으므로 하루 더
    
    print("VIX 데이터 다운로드 중 (Yahoo Finance)...")
    
    # VIX 현물 지수 다운로드
    vix = yf.download("^VIX", start=start_date, end=end_date, progress=False)
    
    if vix.empty:
        print("❌ VIX 데이터를 다운로드할 수 없습니다.")
        return
    
    # 데이터 정리
    vix = vix.reset_index()
    vix = vix.rename(columns={"Date": "date", "Close": "VIX"})
    vix = vix[["date", "VIX"]]
    
    # VIX가 이미 숫자형이므로 변환 불필요
    
    # F1, F2 근사 생성
    # 실제 VIX 선물은 contango/backwardation 상태에 따라 변동하지만
    # 연구용으로 간단한 근사 사용:
    # - Contango 상태 (평균): F1 = VIX * 1.05, F2 = VIX * 1.10
    # - 실제로는 VIX 레벨에 따라 동적으로 조정
    
    vix["F1"] = vix["VIX"] * 1.05
    vix["F2"] = vix["VIX"] * 1.10
    
    # 날짜만 남기기
    vix["date"] = pd.to_datetime(vix["date"]).dt.date
    
    # 저장
    output_path = "data/vix_futures.csv"
    vix.to_csv(output_path, index=False)
    
    print(f"\n✅ VIX 데이터 저장 완료: {output_path}")
    print(f"   총 {len(vix)} 레코드")
    print(f"   기간: {vix['date'].min()} ~ {vix['date'].max()}")
    print(f"\n⚠️  F1, F2는 VIX 현물 기반 근사값입니다 (F1=VIX*1.05, F2=VIX*1.10)")
    print("   실제 VIX 선물 데이터가 필요하면 CBOE 또는 전문 데이터 공급업체 사용 필요")
    print("\n샘플 데이터:")
    print(vix.head(10))

if __name__ == "__main__":
    main()
