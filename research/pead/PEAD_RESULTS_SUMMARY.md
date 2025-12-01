# PEAD (Post-Earnings Announcement Drift) 분석 결과 요약

**실행 날짜**: 2024-12-01  
**데이터 기간**: 2015-2025  
**분석 프레임워크**: RealEval Split (Train/Val/Test)

---

## 📊 실행 요약

### 데이터셋
- **펀더멘털 데이터**: `/home/ubuntu/ares7-ensemble/data/fundamentals.csv`
- **가격 데이터**: 
  - `/home/ubuntu/ares7-ensemble/data/prices.csv`
  - `/home/ubuntu/ml9-quant-strategy/.../price_data_2015_2020_polygon.csv`
  - `/home/ubuntu/ml9-quant-strategy/.../price_data_sp100_2021_2024.csv`
- **벤치마크**: S&P 500 지수 (SPX)

### 이벤트 통계
- **총 이벤트 수**: 7,583개
- **이벤트 정의**: 재무 공시 (fundamentals.csv의 report_date 기준)
- **서프라이즈 정의**: ΔROE, Δgross_margin, Δdebt_to_equity 기반 멀티팩터 z-score

### 버킷 정의
- **pos_top**: 상위 20% 서프라이즈 (긍정적 서프라이즈)
- **neg_bottom**: 하위 20% 서프라이즈 (부정적 서프라이즈)
- **neutral**: 중간 60%

### 분석 기간 (RealEval Split)
- **Train**: 2015-01-01 ~ 2018-12-31
- **Val**: 2019-01-01 ~ 2021-12-31
- **Test**: 2022-01-01 ~ 2025-11-18

---

## 🎯 주요 결과

### 1. 이벤트 단위 PEAD 통계

#### Validation Period (2019-2021)

| Bucket | Horizon | N Events | Mean Excess Ret | Std | Sharpe | t-stat | Win Rate |
|--------|---------|----------|-----------------|-----|--------|--------|----------|
| **pos_top** | 3d | 83 | +0.xx% | x.xx% | 0.145 | 1.319 | 54.2% |
| **pos_top** | 5d | 83 | +0.xx% | x.xx% | 0.140 | 1.275 | 51.8% |
| **pos_top** | 10d | 83 | +0.xx% | x.xx% | 0.145 | 1.320 | 55.4% |
| **neg_bottom** | 3d | 45 | +0.xx% | x.xx% | 0.242 | 1.623 | 46.7% |
| **neg_bottom** | 5d | 45 | +0.xx% | x.xx% | 0.306 | 2.050 | 40.0% |
| **neg_bottom** | 10d | 45 | +0.xx% | x.xx% | 0.245 | 1.641 | 46.7% |

**Validation 기간 해석**:
- **pos_top**: 긍정적 서프라이즈 이벤트 후 3/5/10일 동안 양의 초과 수익률 (Sharpe ~0.14)
- **neg_bottom**: 부정적 서프라이즈 이벤트도 양의 초과 수익률 (Sharpe ~0.24-0.31) → **역설적 결과**
- t-stat이 1.3~2.0 수준으로 통계적 유의성은 제한적

#### Test Period (2022-2025)

| Bucket | Horizon | N Events | Mean Excess Ret | Std | Sharpe | t-stat | Win Rate |
|--------|---------|----------|-----------------|-----|--------|--------|----------|
| **pos_top** | 3d | 292 | +0.xx% | x.xx% | 0.012 | 0.202 | 50.0% |
| **pos_top** | 5d | 292 | +0.xx% | x.xx% | 0.068 | 1.164 | 50.3% |
| **pos_top** | 10d | 292 | -0.xx% | x.xx% | -0.004 | -0.065 | 44.2% |
| **neg_bottom** | 3d | 162 | -0.xx% | x.xx% | -0.016 | -0.208 | 48.8% |
| **neg_bottom** | 5d | 162 | -0.xx% | x.xx% | -0.035 | -0.451 | 56.8% |
| **neg_bottom** | 10d | 162 | -0.xx% | x.xx% | -0.084 | -1.073 | 58.6% |

**Test 기간 해석**:
- **pos_top**: 5일 horizon에서만 약한 양의 초과 수익률 (Sharpe 0.068)
- **neg_bottom**: 모든 horizon에서 음의 초과 수익률 (Sharpe -0.016 ~ -0.084)
- **Val → Test 성능 저하**: Validation에서 관찰된 PEAD 효과가 Test에서 사라짐
- **Out-of-Sample 일반화 실패**: 전형적인 과적합 또는 시장 체제 변화

---

### 2. Label Shuffle 테스트 (Permutation Test)

Label Shuffle은 이벤트 날짜별로 서프라이즈 라벨을 무작위로 섞어서 200회 반복 실험한 결과입니다. **p-value**는 실제 결과가 무작위 결과보다 우월한 확률을 나타냅니다.

#### Validation Period

| Bucket | Horizon | Sharpe | p-value | 해석 |
|--------|---------|--------|---------|------|
| pos_top | 3d | 0.145 | 0.385 | 무작위보다 약간 우월 (유의하지 않음) |
| pos_top | 5d | 0.140 | 0.315 | 무작위보다 약간 우월 (유의하지 않음) |
| pos_top | 10d | 0.145 | 0.200 | 무작위보다 우월 (p<0.25) |
| neg_bottom | 3d | 0.242 | 0.810 | 무작위와 유사 (유의하지 않음) |
| neg_bottom | 5d | 0.306 | 0.935 | 무작위와 유사 (유의하지 않음) |
| neg_bottom | 10d | 0.245 | 0.895 | 무작위와 유사 (유의하지 않음) |

#### Test Period

| Bucket | Horizon | Sharpe | p-value | 해석 |
|--------|---------|--------|---------|------|
| pos_top | 3d | 0.012 | 0.485 | 무작위와 동일 |
| pos_top | 5d | 0.068 | 0.060 | 무작위보다 우월 (p<0.10) ⭐ |
| pos_top | 10d | -0.004 | 0.180 | 무작위보다 열등 |
| neg_bottom | 3d | -0.016 | 0.320 | 무작위와 유사 |
| neg_bottom | 5d | -0.035 | 0.435 | 무작위와 유사 |
| neg_bottom | 10d | -0.084 | 0.215 | 무작위보다 열등 |

**Label Shuffle 결론**:
- **Test 기간 pos_top 5d**만 p-value 0.060으로 통계적으로 유의미 (p<0.10)
- 나머지 대부분의 결과는 **무작위 라벨과 구별 불가능** (p>0.20)
- **PEAD 효과의 통계적 유의성 부족**

---

### 3. 포트폴리오 단위 PEAD 통계

이벤트 기반 포트폴리오를 구성하여 일별 수익률을 계산한 결과입니다.

| Bucket | Horizon | N Days | Mean Daily Ret | Std Daily Ret | Sharpe | Sharpe Excess | MDD | Total Return |
|--------|---------|--------|----------------|---------------|--------|---------------|-----|--------------|
| **pos_top** | 3d | 842 | x.xx% | x.xx% | x.xx | 0.185 | -30.2% | 128.9% |
| **pos_top** | 5d | 1,187 | x.xx% | x.xx% | x.xx | 0.826 | -34.1% | 129.5% |
| **pos_top** | 10d | 1,824 | x.xx% | x.xx% | x.xx | -0.369 | -36.0% | 145.1% |
| **neg_bottom** | 3d | 296 | x.xx% | x.xx% | x.xx | 1.644 | -10.2% | 107.4% |
| **neg_bottom** | 5d | 471 | x.xx% | x.xx% | x.xx | 0.282 | -18.0% | 90.5% |
| **neg_bottom** | 10d | 891 | x.xx% | x.xx% | x.xx | -0.461 | -19.8% | 126.4% |

**포트폴리오 해석**:
- **pos_top 5d**: Sharpe Excess 0.826으로 가장 우수 ⭐
- **neg_bottom 3d**: Sharpe Excess 1.644로 매우 우수 ⭐⭐
- **10d horizon**: 대부분 음의 Sharpe Excess → 장기 보유 불리
- **MDD**: 모든 전략에서 10~36% 수준의 drawdown 발생

---

## 🔍 핵심 발견사항

### 1. PEAD 효과의 존재 여부
- **Validation 기간**: 약한 PEAD 효과 관찰 (Sharpe 0.14~0.31)
- **Test 기간**: PEAD 효과 거의 소멸 (Sharpe -0.08~0.07)
- **결론**: **Out-of-Sample에서 PEAD 효과 미확인**

### 2. 통계적 유의성
- Label Shuffle 테스트 결과, 대부분의 결과가 **무작위와 구별 불가능** (p>0.20)
- **Test pos_top 5d**만 p=0.060으로 유의미
- **결론**: **통계적으로 유의한 PEAD 효과 부족**

### 3. 역설적 결과 (Validation 기간)
- **neg_bottom (부정적 서프라이즈)**에서도 양의 초과 수익률 발생
- 이는 전통적인 PEAD 이론과 **모순**
- 가능한 원인:
  - 서프라이즈 정의 문제 (ΔROE, Δgross_margin, Δdebt_to_equity 조합)
  - 시장 체제 특성 (2019-2021: 코로나 팬데믹 회복기)
  - 샘플 크기 부족 (Val neg_bottom: 45개 이벤트)

### 4. Horizon 효과
- **3d, 5d**: 상대적으로 양호한 성능
- **10d**: 대부분 음의 Sharpe → **장기 보유 불리**
- **결론**: PEAD 효과는 단기 (3~5일)에 집중

### 5. Val → Test 성능 저하
- Validation에서 관찰된 효과가 Test에서 사라짐
- **과적합** 또는 **시장 체제 변화** (2022-2025: 금리 인상, 경기 침체 우려)

---

## 💡 개선 방향

### 1. 서프라이즈 정의 개선
- **현재**: ΔROE, Δgross_margin, Δdebt_to_equity 멀티팩터 z-score
- **개선안**:
  - **SUE (Standardized Unexpected Earnings)**: 실제 EPS vs 애널리스트 컨센서스
  - **Revenue Surprise**: 실제 매출 vs 컨센서스
  - **Guidance Surprise**: 경영진 가이던스 변화
  - **Analyst Revision**: 애널리스트 추정치 변화

### 2. 이벤트 필터링
- **현재**: 모든 재무 공시 이벤트 포함
- **개선안**:
  - **분기 실적 발표일만 포함** (연간 보고서 제외)
  - **시가총액/유동성 필터**: 대형주만 포함
  - **극단값 제거**: 서프라이즈 ±3σ 이상 제거

### 3. 리스크 관리
- **현재**: 단순 동일 가중 포트폴리오
- **개선안**:
  - **변동성 조정 가중**: 저변동성 종목 비중 증가
  - **Stop-Loss**: MDD 제한 (예: -10%)
  - **Position Sizing**: 서프라이즈 크기에 비례

### 4. 시장 체제 분석
- **현재**: 전체 기간 통합 분석
- **개선안**:
  - **Bull/Bear 시장 구분**: VIX, 시장 수익률 기준
  - **금리 환경 구분**: 저금리 vs 고금리
  - **체제별 전략 최적화**

### 5. 데이터 품질 개선
- **현재**: fundamentals.csv (간소화된 재무 비율)
- **개선안**:
  - **SF1 Full Data**: 150+ 컬럼 활용
  - **실시간 데이터**: 공시 시점 정확도 향상
  - **애널리스트 컨센서스**: FactSet, Bloomberg 데이터

---

## 📁 생성된 파일

### 결과 CSV 파일
1. **pead_v0_event_stats.csv** - 이벤트 단위 통계 (Split/Bucket/Horizon별)
2. **pead_v0_label_shuffle.csv** - Label Shuffle 테스트 결과 (p-value 포함)
3. **pead_v0_portfolio_stats.csv** - 포트폴리오 단위 통계

### 로그 파일
- **pead_run.log** - 전체 실행 로그 (98KB)

### 패키지 구조
```
/home/ubuntu/ares7-ensemble/research/pead/
├── __init__.py
├── config.py
├── price_loader.py
├── event_table_builder_v0.py
├── forward_return.py
├── stats.py
├── portfolio.py
├── label_shuffle.py
├── run_pead_v0.py
├── pead_v0_event_stats.csv
├── pead_v0_label_shuffle.csv
├── pead_v0_portfolio_stats.csv
└── pead_run.log
```

---

## 🎓 결론

### 현재 구현의 한계
1. **통계적 유의성 부족**: 대부분의 결과가 무작위와 구별 불가능
2. **Out-of-Sample 일반화 실패**: Val → Test 성능 저하
3. **서프라이즈 정의 문제**: 전통적 PEAD 이론과 모순되는 결과
4. **데이터 품질**: 간소화된 재무 비율만 사용

### 긍정적 발견
1. **포트폴리오 수준**: pos_top 5d (Sharpe Excess 0.826), neg_bottom 3d (Sharpe Excess 1.644) 우수
2. **단기 효과**: 3~5일 horizon에서 상대적으로 양호한 성능
3. **Test pos_top 5d**: 유일하게 통계적으로 유의미 (p=0.060)

### 최종 권고사항
- **현재 전략**: 실전 트레이딩에 사용하기에는 **부적합**
- **개선 후 재평가**: 위의 개선 방향을 적용한 후 재분석 필요
- **추가 연구**: 
  - SUE 기반 서프라이즈 재정의
  - 시장 체제별 분석
  - 리스크 관리 강화

---

**작성자**: Manus AI  
**실행 환경**: Python 3.11, pandas, numpy  
**실행 시간**: ~5분 (7,583 이벤트, 200회 Label Shuffle)
