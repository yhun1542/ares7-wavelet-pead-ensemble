# ARES8 Wrapper Scripts Documentation

**작성일**: 2025-12-01  
**작성자**: ARES7/ARES8 Research Team  
**목적**: PEAD Only를 프로덕션 전략으로 고정하고, Buyback을 R&D 전용으로 정리

---

## 📋 Executive Summary

본 문서는 ARES8 프로젝트의 최종 의사결정을 반영한 2개의 래퍼 스크립트를 설명합니다.

### 핵심 의사결정

1. **프로덕션 전략**: **PEAD Only Overlay** (Buyback weight = 0)
2. **Buyback 위치**: **R&D 전용** (실험/분석용으로만 유지)
3. **비즈니스 근거**:
   - PEAD 단독 Test Sharpe: **0.504** (충분히 강함)
   - Buyback 단독 Test Sharpe: **0.113** (통계적 유의성 없음, p-value=1.0)
   - PEAD+Buyback 앙상블: **0.510** (미미한 개선, +0.006)
   - **결론**: Buyback은 프로덕션에서 제외, R&D로만 유지

---

## 📁 파일 구조

```
ares7-ensemble/
├── run_buyback_v2_real.py          # Buyback R&D 전용 스크립트
├── run_pead_buyback_ensemble.py    # PEAD+Buyback 분석용 스크립트 (기본 PEAD Only)
├── data/
│   ├── buyback_events.csv          # Buyback 이벤트 (260개 → 175개 필터링)
│   ├── prices.csv                  # 가격 데이터 (100 tickers, 2512 days)
│   ├── pead_event_table_positive.csv  # PEAD 이벤트 (901개)
│   └── ares7_base_weights.csv      # ARES7 Base 포트폴리오 (Vol-weighted)
├── buyback_v2_outputs/             # Buyback R&D 결과
│   ├── summary_v2.csv
│   └── shuffle_v2.csv
└── ensemble_outputs/               # Ensemble 분석 결과
    └── ensemble_summary.csv
```

---

## 🔧 스크립트 1: `run_buyback_v2_real.py`

### 용도
- **Buyback 단독 연구**를 수행하는 R&D 전용 스크립트
- 프로덕션 포트폴리오에는 **직접 연결하지 않음**

### 주요 기능
1. `buyback_events.csv` + `prices.csv` 로드
2. Forward returns 계산 (10d, 20d, 30d, 40d)
3. Split별 성과 요약 (Train/Val/Test)
4. Label shuffle 검증 (n=100)

### 실행 방법
```bash
cd /home/ubuntu/ares7-ensemble
python3.11 run_buyback_v2_real.py
```

### 출력
- **콘솔**: Split × Horizon별 Sharpe, t-stat, win rate
- **CSV**: 
  - `buyback_v2_outputs/summary_v2.csv`
  - `buyback_v2_outputs/shuffle_v2.csv`

### 최신 실행 결과 (2025-12-01)

#### Summary
| split | horizon | n_events | sharpe | t_stat | win_rate |
|-------|---------|----------|--------|--------|----------|
| train | 10d     | 44       | 0.154  | 1.02   | 0.500    |
| train | 30d     | 44       | 0.107  | 0.71   | 0.568    |
| val   | 10d     | 17       | 0.228  | 0.94   | 0.412    |
| val   | 30d     | 17       | 0.101  | 0.42   | 0.588    |
| **test** | **10d** | **67** | **0.045** | **0.37** | **0.537** |
| **test** | **30d** | **67** | **0.113** | **0.92** | **0.537** |

#### Label Shuffle
- **모든 split/horizon에서 p-value = 1.0**
- **통계적 유의성 없음** → Buyback 단독으로는 알파 없음

### 핵심 인사이트
- ✅ Buyback 이벤트: 175개 (7 tickers: AAPL, CVX, GOOGL, JNJ, JPM, MSFT, XOM)
- ❌ Test Sharpe: 0.045~0.113 (약함)
- ❌ Label shuffle p-value: 1.0 (유의성 없음)
- **결론**: Buyback은 단독으로 알파 없음, R&D 전용으로만 유지

---

## 🔧 스크립트 2: `run_pead_buyback_ensemble.py`

### 용도
- **PEAD + Buyback 앙상블 분석**용 스크립트
- 4가지 전략 비교: Base / PEAD / Buyback / Ensemble

### 주요 기능
1. 4가지 전략 백테스트:
   - **Base**: ARES7 Base 포트폴리오 (Vol-weighted)
   - **PEAD**: PEAD Only Overlay
   - **Buyback**: Buyback Only Overlay
   - **Ensemble**: PEAD + Buyback (가중치 조정 가능)
2. Split별 성과 비교 (Train/Val/Test)
3. Incremental Sharpe 계산

### 실행 방법
```bash
cd /home/ubuntu/ares7-ensemble
python3.11 run_pead_buyback_ensemble.py
```

### 출력
- **콘솔**: Strategy × Split별 Sharpe, Ann Return, Max DD
- **CSV**: `ensemble_outputs/ensemble_summary.csv`

### 최신 실행 결과 (2025-12-01)

#### PRODUCTION 모드 (α_pead=1.0, α_bb=0.0)

| strategy | split | sharpe | ann_ret | ann_vol | max_dd   |
|----------|-------|--------|---------|---------|----------|
| base     | train | 1.409  | 0.162   | 0.115   | -0.156   |
| base     | val   | 1.173  | 0.247   | 0.210   | -0.319   |
| **base** | **test** | **0.451** | **0.063** | **0.140** | **-0.183** |
| pead     | train | 1.381  | 0.160   | 0.116   | -0.160   |
| pead     | val   | 1.301  | 0.271   | 0.209   | -0.307   |
| **pead** | **test** | **0.504** | **0.071** | **0.142** | **-0.178** |
| ensemble | train | 1.381  | 0.160   | 0.116   | -0.160   |
| ensemble | val   | 1.301  | 0.271   | 0.209   | -0.307   |
| **ensemble** | **test** | **0.504** | **0.071** | **0.142** | **-0.178** |

**핵심 인사이트**:
- ✅ **PEAD Test Sharpe: 0.504** (Base 대비 +0.053)
- ✅ **Ensemble == PEAD** (α_bb=0.0이므로 예상대로)
- ✅ **PRODUCTION: PEAD Only 전략 확정**

#### R&D 모드 (α_pead=0.6, α_bb=0.4)

| strategy | split | sharpe | ann_ret | ann_vol | max_dd   |
|----------|-------|--------|---------|---------|----------|
| **pead** | **test** | **0.504** | **0.071** | **0.142** | **-0.178** |
| **ensemble** | **test** | **0.510** | **0.072** | **0.142** | **-0.175** |

**핵심 인사이트**:
- Ensemble vs PEAD: **+0.006 Sharpe** (미미한 개선)
- Buyback 추가로 인한 복잡도 증가 대비 효과 미미
- **결론**: Buyback 앙상블은 프로덕션에 불필요

### 모드 전환 방법

#### PRODUCTION 모드 (기본)
```python
# run_pead_buyback_ensemble.py 55-65행
ALPHA_PEAD = 1.0      # PEAD overlay weight
ALPHA_BB = 0.0        # PRODUCTION: Buyback overlay OFF
```

#### R&D 모드 (실험용)
```python
# run_pead_buyback_ensemble.py 55-65행 (주석 해제)
ALPHA_PEAD = 0.6
ALPHA_BB = 0.4
```

---

## 📊 종합 비교표

| 항목 | PEAD Only | Buyback Only | PEAD+Buyback (0.6/0.4) |
|------|-----------|--------------|------------------------|
| **Test Sharpe** | **0.504** | 0.113 | 0.510 |
| **Incremental Sharpe** | **+0.053** | +0.013 | +0.059 |
| **Label Shuffle p-value** | 0.001 (유의) | 1.0 (무의미) | N/A |
| **이벤트 수** | 901 | 175 | 1,076 |
| **복잡도** | 낮음 | 낮음 | 높음 |
| **프로덕션 적합성** | ✅ **채택** | ❌ 기각 | ❌ 기각 |

---

## 🎯 최종 권장사항

### 프로덕션 배포
1. **전략**: PEAD Only Overlay
2. **파라미터**:
   - Tilt Size: 1.5%p
   - Horizon: 30 days
   - Min Rank: 0.0 (상위 10% 이미 필터링됨)
3. **스크립트**: `run_pead_buyback_ensemble.py` (PRODUCTION 모드)

### R&D 유지
1. **Buyback 연구**: `run_buyback_v2_real.py`로 단독 성과 모니터링
2. **앙상블 실험**: `run_pead_buyback_ensemble.py` R&D 모드로 가중치 조정 실험
3. **향후 개선**:
   - Buyback 시그널 개선 (NBY 외 추가 피처)
   - 다른 이벤트 타입 탐색 (Insider Trading, M&A 등)

---

## 🔍 기술적 세부사항

### 데이터 필터링
- **Buyback events**: 260개 → 175개 (BAC, PFE 제외, prices 유니버스 기준)
- **PEAD events**: 901개 (Positive surprise only, 상위 10%)
- **Prices**: 100 tickers, 2512 days (2015-11-23 ~ 2025-11-18)

### Split 정의
```python
TRAIN: 2016-01-01 ~ 2018-12-31
VAL:   2019-01-01 ~ 2021-12-31
TEST:  2022-01-01 ~ 2025-11-18
```

### Pure Tilt 메커니즘
1. 이벤트 발생 시 해당 종목에 +1.5%p 가중치 추가
2. Horizon (30일) 동안 유지
3. Base 포트폴리오 대비 상대적 틸트 (절대 비중 아님)
4. 자동 리밸런싱 (이벤트 종료 시 원복)

### 의존성
- Python 3.11
- pandas, numpy
- `research.pead.event_book.EventBook`
- `research.pead.forward_return.attach_forward_returns`

---

## 📝 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|-----------|
| 2025-12-01 | 1.0 | 초기 버전 작성 (PEAD Only 확정) |

---

## 📧 문의

- **프로젝트**: ARES7/ARES8 Ensemble
- **담당**: Quant Research Team
- **문서**: `/home/ubuntu/ares7-ensemble/WRAPPER_SCRIPTS_README.md`

---

## ✅ 체크리스트

### 프로덕션 배포 전 확인사항
- [ ] `run_pead_buyback_ensemble.py`가 PRODUCTION 모드인지 확인 (α_bb=0.0)
- [ ] `data/` 폴더에 4개 CSV 파일 존재 확인
- [ ] Test 실행하여 Ensemble == PEAD 확인
- [ ] 결과 CSV 저장 경로 확인 (`ensemble_outputs/`)

### R&D 실험 시 확인사항
- [ ] `run_buyback_v2_real.py` 실행하여 최신 Buyback 성과 확인
- [ ] `run_pead_buyback_ensemble.py` R&D 모드로 전환
- [ ] α_pead, α_bb 가중치 조정 후 재실행
- [ ] 결과 비교 및 문서화

---

**END OF DOCUMENT**
