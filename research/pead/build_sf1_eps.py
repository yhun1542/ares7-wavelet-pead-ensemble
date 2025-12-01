# research/pead/build_sf1_eps.py

"""
SF1에서 EPS 히스토리 내려받아
/home/ubuntu/ares7-ensemble/data/sf1_eps.csv
를 생성하는 스크립트.

전제:
- NASDAQ_DATA_LINK_API_KEY 환경변수 설정되어 있어야 함.
- nasdaqdatalink 패키지 설치되어 있어야 함.
"""

import os
import math
import pandas as pd
import nasdaqdatalink

from .config import PRICES_PATHS
from .price_loader import load_price_matrix

OUTPUT_PATH = "/home/ubuntu/ares7-ensemble/data/sf1_eps.csv"

# 필요한 SF1 컬럼
SF1_COLUMNS = ["ticker", "dimension", "datekey", "calendardate", "reportperiod", "eps"]


def get_universe_from_prices():
    """
    price 데이터에서 사용 중인 symbol 리스트 추출.
    ARES7/ARES8 전략에서 이미 쓰는 유니버스와 맞추는 게 목적.
    """
    px = load_price_matrix(PRICES_PATHS)  # date x symbol
    symbols = list(px.columns)
    symbols = [s for s in symbols if isinstance(s, str)]
    symbols = sorted(set(symbols))
    return symbols


def download_sf1_eps_for_universe(universe,
                                  start_calendardate="2010-01-01",
                                  batch_size=50):
    """
    SHARADAR/SF1 테이블에서 EPS 관련 컬럼만 가져온다.
    - dimension='ARQ' (As Reported Quarterly) 기준
    - univers: ticker 리스트
    - start_calendardate 이후만 필터
    """
    all_dfs = []

    # nasdaqdatalink API 키 확인 (있으면 알아서 사용)
    api_key = os.environ.get("NASDAQ_DATA_LINK_API_KEY", None)
    if api_key is None:
        print("WARN: NASDAQ_DATA_LINK_API_KEY 환경변수가 설정되어 있지 않습니다.")
        print("      nasdaqdatalink.ApiConfig.api_key 에 직접 세팅했는지 확인하세요.")

    n = len(universe)
    n_batches = math.ceil(n / batch_size)

    print(f"Total tickers: {n}, batch_size={batch_size}, n_batches={n_batches}")

    for i in range(n_batches):
        batch = universe[i * batch_size:(i + 1) * batch_size]
        print(f"[Batch {i+1}/{n_batches}] downloading {len(batch)} tickers...")

        # SF1 get_table 호출
        df_batch = nasdaqdatalink.get_table(
            "SHARADAR/SF1",
            ticker=batch,
            dimension="ARQ",
            calendardate={"gte": start_calendardate},
            qopts={"columns": SF1_COLUMNS},
            paginate=True,
        )

        if df_batch.empty:
            continue

        all_dfs.append(df_batch)

    if not all_dfs:
        return pd.DataFrame(columns=SF1_COLUMNS)

    df_all = pd.concat(all_dfs, ignore_index=True)

    # 데이터 정리
    df_all = df_all.drop_duplicates(subset=["ticker", "calendardate", "dimension"])

    # 타입 정리
    df_all["datekey"] = pd.to_datetime(df_all["datekey"])
    df_all["calendardate"] = pd.to_datetime(df_all["calendardate"])
    df_all["reportperiod"] = pd.to_datetime(df_all["reportperiod"])

    df_all = df_all.sort_values(["ticker", "datekey"])

    return df_all[SF1_COLUMNS]


def main():
    print("=== Build SF1 EPS CSV ===")

    # 1) 유니버스 추출 (prices에서 symbol 리스트)
    print("Loading universe from prices...")
    universe = get_universe_from_prices()
    print(f"Universe size: {len(universe)}")

    # 2) SF1에서 EPS 데이터 다운로드
    print("Downloading SF1 EPS data from SHARADAR/SF1...")
    df_eps = download_sf1_eps_for_universe(universe)

    print(f"Downloaded rows: {len(df_eps)}")

    if df_eps.empty:
        print("No data downloaded. Check API key / filters.")
        return

    # 3) CSV로 저장
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    df_eps.to_csv(OUTPUT_PATH, index=False)

    print(f"Saved EPS data to: {OUTPUT_PATH}")
    print("=== Done ===")


if __name__ == "__main__":
    main()
