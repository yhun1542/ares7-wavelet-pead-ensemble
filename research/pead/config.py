
# RealEval 스타일 Train/Val/Test 스플릿
REAL_EVAL_SPLIT = {
    "train": ("2015-01-01", "2018-12-31"),
    "val":   ("2019-01-01", "2021-12-31"),
    "test":  ("2022-01-01", "2025-11-18"),
}

# 데이터 경로
FUNDAMENTALS_PATH = "/home/ubuntu/ares7-ensemble/data/fundamentals.csv"

PRICES_PATHS = [
    "/home/ubuntu/ares7-ensemble/data/prices.csv",
    "/home/ubuntu/ml9-quant-strategy/quant-ensemble-strategy/data/price_data_2015_2020_polygon.csv",
    "/home/ubuntu/ml9-quant-strategy/quant-ensemble-strategy/data/price_data_sp100_2021_2024.csv",
]

SPX_CLOSE_PATH = "/home/ubuntu/ml9-quant-strategy/quant-ensemble-strategy/data/spx_close.csv"

# PEAD 관련 경로
EPS_TABLE_PATH = "/home/ubuntu/ares7-ensemble/data/sf1_eps.csv"
BASE_WEIGHTS_PATH = "/home/ubuntu/ares7-ensemble/data/ares7_base_weights.csv"

# 이벤트 서프라이즈 버킷 기준 (상/하위 퍼센타일)
POS_PCT = 0.8
NEG_PCT = 0.2
