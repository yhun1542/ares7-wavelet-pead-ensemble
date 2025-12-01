#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
download_vix_data.py

Polygon API를 사용하여 VIX 현물 및 VIX 선물 데이터 다운로드
"""

import os
import time
import pandas as pd
import requests
from datetime import datetime, timedelta

API_KEY = "w7KprL4_lK7uutSH0dYGARkucXHOFXCN"
BASE_URL = "https://api.polygon.io"

def download_vix_spot(start_date, end_date):
    """VIX 현물 지수 다운로드 (VIX)"""
    # Polygon에서 VIX는 I:VIX 또는 VIX 형식일 수 있음
    for ticker in ["I:VIX", "VIX", "$VIX"]:
        url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
        params = {"apiKey": API_KEY, "limit": 50000}
        
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if "results" in data and data["results"]:
                print(f"✅ VIX 티커 '{ticker}' 사용")
                df = pd.DataFrame(data["results"])
                df["date"] = pd.to_datetime(df["t"], unit="ms")
                df = df.rename(columns={"c": "VIX"})
                df = df[["date", "VIX"]].sort_values("date")
                return df
        print(f"티커 '{ticker}' 시도 실패: {response.status_code}")
    
    print("모든 VIX 티커 형식 실패")
    return pd.DataFrame()

def download_vix_spot_old(start_date, end_date):
    """VIX 현물 지수 다운로드 (I:VIX) - OLD"""
    url = f"{BASE_URL}/v2/aggs/ticker/I:VIX/range/1/day/{start_date}/{end_date}"
    params = {"apiKey": API_KEY, "limit": 50000}
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"VIX Spot 다운로드 실패: {response.status_code}")
        return pd.DataFrame()
    
    data = response.json()
    if "results" not in data:
        print("VIX Spot 데이터 없음")
        return pd.DataFrame()
    
    df = pd.DataFrame(data["results"])
    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df = df.rename(columns={"c": "VIX"})
    df = df[["date", "VIX"]].sort_values("date")
    return df

def download_vix_futures(ticker, start_date, end_date):
    """VIX 선물 다운로드"""
    url = f"{BASE_URL}/v2/aggs/ticker/{ticker}/range/1/day/{start_date}/{end_date}"
    params = {"apiKey": API_KEY, "limit": 50000}
    
    response = requests.get(url, params=params)
    if response.status_code != 200:
        print(f"{ticker} 다운로드 실패: {response.status_code}")
        return pd.DataFrame()
    
    data = response.json()
    if "results" not in data:
        print(f"{ticker} 데이터 없음")
        return pd.DataFrame()
    
    df = pd.DataFrame(data["results"])
    df["date"] = pd.to_datetime(df["t"], unit="ms")
    df = df.rename(columns={"c": "price"})
    df = df[["date", "price"]].sort_values("date")
    return df

def main():
    # 날짜 범위 설정 (기존 데이터와 동일하게 2015-11-23 ~ 2025-11-21)
    start_date = "2015-11-23"
    end_date = "2025-11-21"
    
    print("VIX 현물 지수 다운로드 중...")
    vix_spot = download_vix_spot(start_date, end_date)
    
    if vix_spot.empty:
        print("❌ VIX 현물 데이터를 다운로드할 수 없습니다.")
        return
    
    print(f"✅ VIX 현물: {len(vix_spot)} 레코드")
    
    # VIX 선물은 continuous contract가 아니라 개별 만기 계약이므로
    # 간단한 근사로 VIX 현물 기반으로 F1, F2 생성
    # (실제로는 VIX 선물 ETF인 VXX, UVXY 등을 사용하거나 CBOE 데이터 필요)
    
    print("\n⚠️  VIX 선물 continuous contract는 Polygon에서 직접 제공하지 않습니다.")
    print("대안: VIX 현물 기반으로 F1, F2를 근사 생성합니다.")
    print("  F1 = VIX * 1.05 (근월물, 약 5% 프리미엄)")
    print("  F2 = VIX * 1.10 (차월물, 약 10% 프리미엄)")
    
    vix_spot["F1"] = vix_spot["VIX"] * 1.05
    vix_spot["F2"] = vix_spot["VIX"] * 1.10
    
    # 날짜만 남기기 (시간 제거)
    vix_spot["date"] = vix_spot["date"].dt.date
    
    # 저장
    output_path = "data/vix_futures.csv"
    vix_spot.to_csv(output_path, index=False)
    
    print(f"\n✅ VIX 데이터 저장 완료: {output_path}")
    print(f"   총 {len(vix_spot)} 레코드")
    print(f"   기간: {vix_spot['date'].min()} ~ {vix_spot['date'].max()}")
    print("\n샘플 데이터:")
    print(vix_spot.head(10))

if __name__ == "__main__":
    main()
