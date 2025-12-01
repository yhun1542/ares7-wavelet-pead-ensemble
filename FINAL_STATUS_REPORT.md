# ARES-7 Ensemble 최종 상황 보고서

**날짜**: 2025-11-26  
**목표**: Sharpe ratio 2.0+  
**현재 최고 성능**: Sharpe 0.886 (3-Way Ensemble)  
**목표 대비 부족**: 1.114

---

## 검증 완료된 엔진 (Look-ahead Bias 없음)

### 1. Low-Vol v2 Final
- **파일**: `engine_c_lowvol_v2_final.py`
- **Sharpe**: 0.808
- **Annual Return**: 11.79%
- **Annual Vol**: 14.58%
- **MDD**: -27.56%
- **전략**: Low Risk (70%) + Quality (30%), 60일 리밸런싱
- **상태**: ✅ 검증 완료 (원본 확인)

### 2. Momentum Simple v1
- **파일**: `engine_momentum_simple_v1.py`
- **Sharpe**: 0.806
- **Annual Return**: 16.10%
- **Annual Vol**: 19.97%
- **MDD**: -32.72%
- **전략**: 12개월 momentum (1개월 skip), 20일 리밸런싱
- **상태**: ✅ 검증 완료 (새로 개발)

### 3. Mean Reversion v1
- **파일**: `engine_mean_reversion_v1.py`
- **Sharpe**: 0.795
- **Annual Return**: 18.42%
- **Annual Vol**: 23.19%
- **MDD**: -43.59%
- **전략**: RSI-based oversold, 5일 리밸런싱
- **상태**: ✅ 검증 완료 (새로 개발)

### 4. A+LS v2 (원본 발견!)
- **파일**: `als_v2_complete/als_signal_v2.py`
- **Sharpe**: 0.782
- **Annual Return**: 13.15%
- **Annual Vol**: 16.81%
- **MDD**: -32.26%
- **전략**: Momentum (50%) + Mean Reversion (50%), 5일 리밸런싱
- **상태**: ✅ 검증 완료 (원본 확인)
- **출처**: EC2 서버 + `als_v2_complete.tar.gz`

---

## 상관관계 분석

|             | LowVol v2 | Momentum v1 | MeanRev v1 | A+LS v2 |
|-------------|-----------|-------------|------------|---------|
| LowVol v2   | 1.000     | 0.840       | 0.693      | 0.874   |
| Momentum v1 | 0.840     | 1.000       | 0.678      | 0.826   |
| MeanRev v1  | 0.693     | 0.678       | 1.000      | 0.707   |
| A+LS v2     | 0.874     | 0.826       | 0.707      | 1.000   |

**핵심 문제**: 모든 엔진 간 상관관계가 매우 높음 (0.68-0.87)

**원인**:
1. 모두 long-only 전략
2. 같은 유니버스 (100 stocks)
3. 비슷한 시그널 (momentum, mean reversion)

---

## 앙상블 조합 테스트 결과

| 조합 | Sharpe | Return | Vol | MDD |
|------|--------|--------|-----|-----|
| **3-Way: LowVol + Momentum + MeanRev** | **0.886** | **15.44%** | **17.43%** | **-33.82%** |
| 4-Way: Equal Weight | 0.881 | 14.87% | 16.87% | -33.42% |
| 4-Way: Optimized 1 (30/30/20/20) | 0.879 | 14.68% | 16.69% | -32.75% |
| 4-Way: Optimized 2 (40/20/20/20) | 0.879 | 14.25% | 16.22% | -32.22% |

**최고 성능**: 3-Way Equal Weight (33% / 33% / 33%)

**결론**: A+LS v2를 추가해도 성능 개선 효과 미미 (오히려 약간 하락)

---

## 원본 파일 탐색 결과

### EC2 서버 탐색 (3.35.141.47)

1. **A+LS Enhanced 원본 발견** ✅
   - 위치: `~/ares7_a_ls_v2_package/fast_backtest_v80.py`
   - 패키지: `als_v2_complete.tar.gz`
   - 검증: 원본 코드 실행 성공 (Sharpe 0.782)

2. **C1 엔진들**
   - 위치: `~/ares7_c1_engines/`
   - 여러 버전 존재: c1_equal_ls.py, c1_mvo_*.py, c1_robust_*.py
   - 상태: 어떤 버전이 C1 Final v5인지 불명확

3. **Factor 엔진**
   - 상태: 원본 파일 찾지 못함

### 기존 JSON 파일 분석

- `engine_ls_enhanced_results.json` (Sharpe 0.947)
  - 원본 코드 실행 결과 (Sharpe 0.782)와 불일치
  - 다른 버전 또는 다른 파라미터로 생성된 것으로 추정

- `C1_final_v5.json` (Sharpe 0.715)
  - 원본 코드 없음
  - engine_c1_v6_simple.py 실행 시 Sharpe -0.549

- `Factor_final.json` (Sharpe 0.555)
  - 원본 코드 없음
  - engine_factor_v2_pit.py 실행 시 Sharpe -0.400

---

## 실패한 시도

### Factor Long-Short v1
- **파일**: `engine_factor_longshort_v1.py`
- **Sharpe**: -0.285 (실패)
- **문제**: 
  - Sector 정보 부정확 (하드코딩)
  - Fundamental 데이터 부족
  - Long-Short 구현 복잡도

---

## Sharpe 2.0 미달성 원인 분석

### 1. 높은 상관관계
- 모든 엔진이 0.68-0.87 상관관계
- 다각화 효과 제한적
- 앙상블 효과 미미

### 2. 같은 방향성
- 모두 long-only 전략
- 시장 베타 높음
- 시장 하락 시 모두 손실

### 3. 같은 유니버스
- 100개 동일 종목
- 같은 시장 환경
- 제한적인 기회

---

## Sharpe 2.0 달성 방안

### Option A: Long-Short 전략 추가 ⭐⭐⭐ 최우선
**목표**: 상관관계 낮추기

**전략**:
1. **Sector-Neutral Long-Short**
   - 각 섹터 내에서 Long/Short
   - 시장 중립적
   - 낮은 베타

2. **Pairs Trading**
   - 상관관계 높은 종목 쌍
   - 스프레드 거래
   - 시장 중립적

3. **Statistical Arbitrage**
   - 통계적 이상 신호
   - 평균 회귀
   - 높은 회전율

**예상 효과**:
- Long-only와 상관관계 < 0.3
- 5-Way Ensemble Sharpe 1.2-1.5

**과제**:
- Sector 정보 필요
- 구현 복잡도 높음
- 검증 시간 필요

### Option B: 다른 자산군 추가 ⭐⭐
**목표**: 완전히 다른 수익원

**전략**:
1. **채권 (Bonds)**
   - TLT (장기 국채)
   - 주식과 낮은 상관관계
   - 안정적 수익

2. **원자재 (Commodities)**
   - 금, 원유 등
   - 인플레이션 헤지
   - 낮은 상관관계

3. **섹터 로테이션**
   - 섹터 ETF
   - 경기 사이클 활용
   - 중간 상관관계

**예상 효과**:
- Multi-asset Ensemble Sharpe 1.0-1.3

**과제**:
- 데이터 준비 필요
- 다른 리밸런싱 주기
- 자산 배분 최적화

### Option C: 레버리지 활용 ⭐
**목표**: 변동성 조정 후 수익 증폭

**방법**:
- 현재 3-Way Ensemble Vol 17.43%
- Target Vol 35% (2.0x 레버리지)
- Sharpe 유지 시 Return 2배

**계산**:
- 현재: Sharpe 0.886, Return 15.44%, Vol 17.43%
- 2.0x: Sharpe 0.886, Return 30.88%, Vol 34.86%

**문제**:
- MDD 증가 (-33.82% → -67%+)
- 레버리지 비용 (이자, 수수료)
- 리스크 관리 복잡
- 실제 Sharpe 하락 가능

### Option D: 파라미터 최적화 ⚠️
**목표**: 각 엔진 파라미터 튜닝

**방법**:
- Momentum lookback/skip 조정
- Mean Reversion RSI threshold 조정
- 리밸런싱 주기 최적화
- 가중치 최적화

**문제**:
- Overfitting 위험 매우 높음
- Out-of-sample 성능 하락
- 큰 성능 향상 기대 어려움

---

## 추천 로드맵

### Phase 1: Long-Short 전략 개발 (최우선)
1. **Sector 정보 확보**
   - GICS 섹터 분류
   - 또는 간단한 업종 분류

2. **Simple Long-Short 구현**
   - Factor-based (Value, Quality, Momentum)
   - Sector-neutral
   - 목표: Sharpe 0.8+, 상관관계 < 0.3

3. **5-Way Ensemble 테스트**
   - LowVol + Momentum + MeanRev + A+LS + LongShort
   - 목표: Sharpe 1.2-1.5

### Phase 2: 추가 전략 (필요 시)
1. **Pairs Trading** 또는 **Statistical Arbitrage**
2. **6-Way Ensemble**
3. 목표: Sharpe 1.5-1.8

### Phase 3: 최종 조정
1. **가중치 최적화**
2. **레버리지 고려** (필요 시)
3. 목표: Sharpe 2.0+

---

## 기술적 검증 사항

### ✅ 확인된 사항
1. **Look-ahead Bias 제거**: 모든 엔진에서 `weights.shift(1)` 또는 `shift(1)` 사용
2. **데이터 정합성**: 2015-2025, 100 stocks, 일관된 데이터
3. **거래 비용**: 0.05% 적용
4. **백테스트 프레임워크**: 일관된 구조
5. **원본 코드 확인**: A+LS v2, Low-Vol v2 원본 확인

### ⚠️ 주의 사항
1. **Overfitting**: 파라미터 최적화 시 주의
2. **Out-of-Sample**: 별도 테스트 필요
3. **실전 적용**: 슬리피지, 마켓 임팩트 추가 고려
4. **Sector 정보**: Long-Short 전략에 필수

---

## 파일 목록

### 검증된 엔진
- `engine_c_lowvol_v2_final.py` (Sharpe 0.808)
- `engine_momentum_simple_v1.py` (Sharpe 0.806)
- `engine_mean_reversion_v1.py` (Sharpe 0.795)
- `als_v2_complete/als_signal_v2.py` (Sharpe 0.782)

### 결과 파일
- `results/engine_c_lowvol_v2_final_results.json`
- `results/engine_momentum_simple_v1_results.json`
- `results/engine_mean_reversion_v1_results.json`
- `results/als_v2_stats.json`
- `results/als_v2_returns.csv`

### 프레임워크
- `gpt_backtester_v4.py` (백테스트 프레임워크)

### 데이터
- `data/price_full.csv` (100 stocks, 2015-2025)
- `data/fundamentals.csv` (fundamental data)

### EC2 다운로드
- `engine_a_ls_original.py` (fast_backtest_v80.py)
- `ec2_c1_engines/` (C1 엔진들)

---

## 결론

### 현재 상황
- 4개의 검증된 long-only 엔진으로 Sharpe 0.886 달성
- 목표 Sharpe 2.0에 1.114 부족
- 원본 파일 대부분 확인 (A+LS v2, Low-Vol v2)

### 핵심 문제
- **높은 상관관계** (0.68-0.87)로 인한 제한적인 앙상블 효과
- 모두 long-only, 같은 유니버스

### 해결책
- **Long-Short 전략 추가**로 상관관계를 낮추고 앙상블 효과 극대화
- Sector-neutral Long-Short가 가장 유망

### 다음 단계
1. Sector 정보 확보
2. Simple Long-Short 엔진 개발
3. 5-Way Ensemble 테스트
4. 필요 시 추가 전략 개발

---

**작성자**: Manus AI  
**최종 업데이트**: 2025-11-26 11:30 KST  
**상태**: Long-Short 전략 개발 대기 중
