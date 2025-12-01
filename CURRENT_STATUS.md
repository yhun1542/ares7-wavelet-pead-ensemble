# ARES-7 프로젝트 현재 상황 보고

## 날짜: 2025-11-25

## 요약

**목표**: Sharpe ratio 2.0+ 달성  
**현재 최고 성능**: Sharpe 0.886 (3-Way Equal Weight Ensemble)  
**목표 대비 부족**: 1.114

---

## 검증된 엔진 (Look-ahead Bias 없음)

### 1. Low-Vol v2 Final
- **파일**: `engine_c_lowvol_v2_final.py`
- **Sharpe**: 0.808
- **Annual Return**: 11.79%
- **Annual Vol**: 14.58%
- **MDD**: -27.56%
- **전략**: Low Risk (70%) + Quality (30%), 60일 리밸런싱
- **상태**: ✅ 검증 완료

### 2. Momentum Simple v1
- **파일**: `engine_momentum_simple_v1.py`
- **Sharpe**: 0.806
- **Annual Return**: 16.10%
- **Annual Vol**: 19.97%
- **MDD**: -32.72%
- **전략**: 12개월 momentum (1개월 skip), 20일 리밸런싱
- **상태**: ✅ 검증 완료

### 3. Mean Reversion v1
- **파일**: `engine_mean_reversion_v1.py`
- **Sharpe**: 0.795
- **Annual Return**: 18.42%
- **Annual Vol**: 23.19%
- **MDD**: -43.59%
- **전략**: RSI-based oversold, 5일 리밸런싱
- **상태**: ✅ 검증 완료

---

## 상관관계 분석

|          | LowVol | Momentum | MeanRev |
|----------|--------|----------|---------|
| LowVol   | 1.000  | 0.840    | 0.693   |
| Momentum | 0.840  | 1.000    | 0.678   |
| MeanRev  | 0.693  | 0.678    | 1.000   |

**문제점**: 모든 엔진 간 상관관계가 높음 (0.68-0.84)
- 이유: 모두 long-only, 같은 유니버스(100 stocks)
- 결과: 앙상블 효과 제한적

---

## 앙상블 조합 테스트 결과

| 조합 | Sharpe | Return | Vol | MDD |
|------|--------|--------|-----|-----|
| 2-Way: LowVol + Momentum | 0.841 | 13.94% | 16.59% | -30.03% |
| 2-Way: LowVol + MeanRev | 0.865 | 15.10% | 17.46% | -34.71% |
| 2-Way: Momentum + MeanRev | 0.873 | 17.26% | 19.77% | -36.98% |
| **3-Way: Equal Weight** | **0.886** | **15.44%** | **17.43%** | **-33.82%** |
| 3-Way: Optimized 1 (40/30/30) | 0.885 | 15.07% | 17.02% | -33.18% |
| 3-Way: Optimized 2 (50/25/25) | 0.883 | 14.52% | 16.45% | -32.22% |

**최고 성능**: 3-Way Equal Weight (33% / 33% / 33%)

---

## 기각된 엔진들 (Look-ahead Bias 발견)

### 원본 4-Way Ensemble 엔진들
1. **A+LS Enhanced** (JSON Sharpe 0.947)
   - 원본 코드 없음
   - JSON 결과는 look-ahead bias 버전

2. **C1 Final v5** (JSON Sharpe 0.715)
   - 원본 코드 없음
   - engine_c1_v6_simple.py 실행 시 Sharpe -0.549

3. **Factor Final** (JSON Sharpe 0.555)
   - 원본 코드 없음
   - engine_factor_v2_pit.py 실행 시 Sharpe -0.400

**결론**: 기존 JSON 파일들은 모두 look-ahead bias가 있는 버전의 결과

---

## 문제점 및 원인 분석

### 1. Sharpe 2.0 미달성 원인
- **높은 상관관계**: 모든 엔진이 0.68-0.84 상관관계
- **같은 방향성**: 모두 long-only 전략
- **같은 유니버스**: 100개 동일 종목

### 2. 앙상블 효과 제한
- 다각화 효과가 제한적
- 개별 엔진 Sharpe 0.8 수준에서 앙상블 Sharpe 0.9까지만 향상

---

## 다음 단계 옵션

### Option A: Long-Short 전략 추가 ⭐ 추천
**목표**: 상관관계 낮추기
- Factor Long-Short (sector-neutral)
- Pairs Trading
- Statistical Arbitrage

**장점**:
- Long-only와 낮은 상관관계 기대
- 시장 중립적 수익
- 앙상블 효과 극대화

**단점**:
- 구현 복잡도 높음
- 검증 시간 필요

### Option B: 레버리지 활용
**목표**: 변동성 조정 후 레버리지로 수익 증폭
- 현재 3-Way Ensemble Vol 17.43%
- 2.0x 레버리지 적용 시 Sharpe 유지하면서 Return 2배

**장점**:
- 빠른 구현
- 이론적으로 Sharpe 유지

**단점**:
- 실제 레버리지 비용 고려 필요
- MDD 증가 (현재 -33.82% → -67%+)
- 리스크 관리 복잡

### Option C: 파라미터 최적화
**목표**: 각 엔진의 파라미터 튜닝
- Momentum lookback/skip 조정
- Mean Reversion RSI threshold 조정
- 리밸런싱 주기 최적화

**장점**:
- 기존 프레임워크 활용
- 점진적 개선

**단점**:
- Overfitting 위험
- 큰 성능 향상 기대 어려움

### Option D: 새로운 데이터 소스
**목표**: ETF, 섹터 데이터 활용
- 섹터 로테이션
- Multi-asset (주식 + 채권 + 원자재)
- Alternative data

**장점**:
- 완전히 다른 수익원
- 낮은 상관관계

**단점**:
- 데이터 준비 필요
- 개발 시간 소요

---

## 추천 방안

### 1단계: Long-Short 엔진 개발 (최우선)
- Factor Long-Short (sector-neutral)
- 목표: Sharpe 1.0+, 기존 엔진과 상관관계 < 0.3
- 예상 4-Way Ensemble Sharpe: 1.2-1.5

### 2단계: 추가 Long-Short 엔진
- Pairs Trading 또는 Statistical Arbitrage
- 목표: 5-Way Ensemble Sharpe 1.5-1.8

### 3단계: 레버리지 또는 최적화
- 필요시 적용하여 Sharpe 2.0+ 달성

---

## 기술적 검증 사항

### ✅ 확인된 사항
1. **Look-ahead Bias 제거**: 모든 엔진에서 `weights.shift(1)` 사용
2. **데이터 정합성**: 2015-2025, 100 stocks, 일관된 데이터
3. **거래 비용**: 0.05% 적용
4. **백테스트 프레임워크**: 일관된 구조

### ⚠️ 주의 사항
1. **Overfitting**: 파라미터 최적화 시 주의
2. **Out-of-Sample**: 별도 테스트 필요
3. **실전 적용**: 슬리피지, 마켓 임팩트 추가 고려

---

## 파일 목록

### 검증된 엔진
- `engine_c_lowvol_v2_final.py` (Sharpe 0.808)
- `engine_momentum_simple_v1.py` (Sharpe 0.806)
- `engine_mean_reversion_v1.py` (Sharpe 0.795)

### 결과 파일
- `results/engine_c_lowvol_v2_final_results.json`
- `results/engine_momentum_simple_v1_results.json`
- `results/engine_mean_reversion_v1_results.json`

### 프레임워크
- `gpt_backtester_v4.py` (백테스트 프레임워크)

### 데이터
- `data/price_full.csv` (100 stocks, 2015-2025)
- `data/fundamentals.csv` (fundamental data)

---

## 결론

현재 3개의 검증된 long-only 엔진으로 Sharpe 0.886을 달성했으나, 목표 Sharpe 2.0에는 1.114 부족합니다.

**핵심 문제**: 높은 상관관계 (0.68-0.84)로 인한 제한적인 앙상블 효과

**해결책**: Long-Short 전략 추가로 상관관계를 낮추고 앙상블 효과를 극대화해야 합니다.

다음 단계는 **Factor Long-Short 엔진 개발**을 추천합니다.
