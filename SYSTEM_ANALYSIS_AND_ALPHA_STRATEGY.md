# 지속적 알파와 높은 샤프니스 달성 전략

## Executive Summary

현재까지의 연구 결과(PEAD v1, ARES8 Overlay)를 바탕으로, **지속적인 알파와 높은 샤프니스를 달성하기 위한 체계적인 전략**을 제시합니다.

**핵심 발견**:
- PEAD 시그널 자체는 **약한 양의 알파 보유** (Gross Sharpe 0.05~0.48)
- Overlay 구현에서 **거래비용이 알파를 완전히 잠식** (Net Sharpe -0.65)
- Equal-Weight Base의 **구조적 한계** (팩터 중립성 부재)

**목표**:
1. **지속적 알파**: Train/Val/Test 전 기간에서 양의 초과수익
2. **높은 샤프니스**: Incremental Sharpe ≥ 0.3 (Net 기준)
3. **낮은 MDD**: 추가 손실 ≤ 3%p

---

## Part 1: 현재 시스템 분석

### 1.1 ARES7 Base 시스템 (현재 상태)

#### 강점
- **높은 Sharpe Ratio**: 0.9+ (Equal-Weight 기준)
- **안정적 수익**: 연간 15.4%
- **낮은 MDD**: -33.1%

#### 약점
- **팩터 노출 불명확**: Equal-Weight는 팩터 중립적이지 않음
- **Overlay 여지 부족**: 이미 높은 Sharpe로 개선 어려움
- **실제 ARES7 weight 부재**: 진짜 weight matrix 필요

---

### 1.2 PEAD v1 (EPS Surprise) 분석

#### 이벤트 단위 성과

| Split | Mean Ret | Sharpe | p-value | 평가 |
|-------|----------|--------|---------|------|
| **Val (pos_top 3d)** | +0.55% | **0.257** | **0.03** | ⭐⭐⭐ 강력 |
| **Test (pos_top 3d)** | +0.17% | 0.057 | 0.10 | ⭐ 약함 |
| **Val (pos_top 5d)** | +0.78% | **0.265** | 0.17 | ⭐⭐ 중간 |

#### 포트폴리오 단위 성과

| Horizon | Sharpe Excess | Total Return | 평가 |
|---------|---------------|--------------|------|
| **pos_top 3d** | **0.902** | 248% | ⭐⭐⭐ 우수 |
| **pos_top 5d** | **0.880** | 336% | ⭐⭐⭐ 우수 |

#### 핵심 문제점

1. **Val → Test 성능 저하**
   - Val Sharpe 0.26 → Test Sharpe 0.06
   - Out-of-Sample 일반화 실패

2. **통계적 유의성 부족**
   - Test p-value 0.10 (경계선)
   - 무작위와 구별 어려움

3. **알파 크기 작음**
   - 평균 초과수익 0.17~0.55%
   - 거래비용 대비 미약

---

### 1.3 ARES8 Overlay 분석

#### Gross vs Net 비교 (Budget=5%, Horizon=10d, MinRank=0.9)

| Metric | Gross (fee=0) | Net (fee=0.001) | 차이 |
|--------|---------------|-----------------|------|
| **All Incremental Sharpe** | **+0.071** | **-0.651** | -0.722 |
| **Val Incremental Sharpe** | **+0.485** | **-0.157** | -0.643 |
| **Test Incremental Sharpe** | **+0.233** | **-0.439** | -0.672 |
| **All Incremental Ann Ret** | **+0.040%** | **-0.36%** | -0.40% |

#### 핵심 문제점

1. **거래비용 과다**
   - 추정 연간 Turnover: ~312%
   - 추정 연간 거래비용: ~0.62%
   - **거래비용 >> PEAD 알파** (0.62% vs 0.04%)

2. **Equal-Weight Base 한계**
   - Small-cap tilt, High volatility tilt
   - 팩터 중립성 부재
   - PEAD 시그널과 상호작용 불명확

3. **Budget/Horizon 최적화 부족**
   - Budget 5%도 과도할 가능성
   - Horizon 10d가 최적인지 미검증
   - MinRank 0.9의 효과 제한적

---

## Part 2: 지속적 알파 달성 전략

### 2.1 핵심 원칙

#### Principle 1: **팩터 중립성 확보**

**문제**: Equal-Weight Base는 팩터 노출이 불명확
- Size factor: Small-cap tilt
- Volatility factor: High vol tilt
- Momentum factor: 불명확

**해결책**: **진짜 ARES7 weight matrix 사용**
- ARES7은 이미 팩터 최적화되어 있음
- Overlay는 **순수 PEAD 알파만** 추가
- 팩터 노출 변화 최소화

**예상 효과**:
- Gross Incremental Sharpe: 0.07 → **0.2~0.3**
- Net Incremental Sharpe: -0.65 → **-0.1~+0.1**

---

#### Principle 2: **거래비용 최소화**

**문제**: 거래비용 0.62% >> PEAD 알파 0.04%

**해결책 A: Horizon 연장**
- 현재: 10d
- 목표: **15~20d**
- 효과: Turnover 50% 감소 → 거래비용 50% 감소

**해결책 B: Budget 축소**
- 현재: 5%
- 목표: **2~3%**
- 효과: Turnover 40% 감소 → 거래비용 40% 감소

**해결책 C: MinRank 상향**
- 현재: 0.9
- 목표: **0.95**
- 효과: 더 강한 서프라이즈만 선택 → 알파 증가

**해결책 D: Fee Rate 재측정**
- 현재 가정: 0.1% (편도)
- 실제 가능: **0.05%** (대형주, 높은 유동성)
- 효과: 거래비용 50% 감소

**종합 효과**:
- 현재 거래비용: 0.62%
- 최적화 후: **0.15~0.20%**
- **거래비용 < PEAD 알파** 달성 가능

---

#### Principle 3: **시그널 품질 개선**

**문제**: PEAD 알파가 약함 (Gross 0.04%)

**해결책 A: SUE (Standardized Unexpected Earnings) 사용**
- 현재: `eps_actual - eps_prev`
- 개선: `(eps_actual - eps_consensus) / std(eps_surprise)`
- 효과: 서프라이즈 크기 정규화 → 비교 가능성 증가

**해결책 B: 분기 실적 발표일만 포함**
- 현재: 모든 EPS 이벤트
- 개선: **분기 실적 발표일만** (연간 보고서 제외)
- 효과: 시장 주목도 높은 이벤트만 선택

**해결책 C: 시장 체제별 분석**
- Bull vs Bear 시장
- 고금리 vs 저금리 환경
- 효과: 체제별 최적 파라미터 적용

**해결책 D: SF1 Full Data 활용**
- 현재: EPS만 사용
- 개선: **Revenue, Margin, Cash Flow** 등 150+ 컬럼
- 효과: 다차원 서프라이즈 시그널

**예상 효과**:
- Gross Incremental Sharpe: 0.07 → **0.3~0.5**
- Val p-value: 0.03 → **0.01**

---

#### Principle 4: **앙상블 전략**

**문제**: 단일 시그널(PEAD)의 한계

**해결책: Multi-Signal Overlay**

**Signal 1: PEAD (EPS Surprise)**
- Horizon: 15d
- Budget: 2%
- MinRank: 0.95

**Signal 2: Buyback Announcements**
- Horizon: 20d
- Budget: 2%
- MinRank: 0.90

**Signal 3: Guidance Revision** (향후)
- Horizon: 10d
- Budget: 1%
- MinRank: 0.95

**Signal 4: Analyst Upgrades/Downgrades** (향후)
- Horizon: 5d
- Budget: 1%
- MinRank: 0.90

**앙상블 방법**:
```python
# Equal-Weight Ensemble
overlay_weight = (
    0.40 * pead_signal +
    0.30 * buyback_signal +
    0.20 * guidance_signal +
    0.10 * analyst_signal
)

# 최종 포트폴리오
final_weight = (
    0.94 * ares7_base_weight +
    0.06 * overlay_weight
)
```

**예상 효과**:
- **신호 다각화** → 안정성 증가
- **상관관계 낮음** → Sharpe 증가
- **총 Budget 6%** → 거래비용 관리 가능

---

### 2.2 구체적 실행 계획

#### Phase 1: ARES7 Base Weight 확보 (최우선)

**목표**: 진짜 ARES7 weight matrix 추출

**방법**:
1. ARES7 백테스트 엔진 찾기
2. 일별 weight matrix 추출
3. CSV로 export
4. 검증 (sum=1, 날짜 연속성)

**예상 소요**: 1-2일

---

#### Phase 2: PEAD 파라미터 최적화

**목표**: Net Incremental Sharpe ≥ 0.2

**Grid Search 범위**:
- Budget: [0.02, 0.03, 0.05]
- Horizon: [10, 15, 20]
- MinRank: [0.90, 0.95]
- Fee: [0.0005, 0.001]

**총 조합**: 3 × 3 × 2 × 2 = **36개**

**실행**:
```bash
python -m research.pead.run_ares8_overlay_sweep \
    --base_type ares7 \
    --budgets 0.02 0.03 0.05 \
    --horizons 10 15 20 \
    --min_ranks 0.90 0.95 \
    --fees 0.0005 0.001 \
    --output data/pead/grid_search_results.csv
```

**예상 소요**: 2-3시간

---

#### Phase 3: Buyback 알파 분석

**목표**: Buyback 시그널의 알파 확인

**방법**:
1. Buyback 이벤트 테이블 생성 (진행 중)
2. H-day alpha 분석 (3/5/10/15/20d)
3. Train/Val/Test Sharpe 확인
4. PEAD와 상관관계 분석

**판단 기준**:
- Test Incremental Sharpe ≥ 0.2 (Gross)
- Test p-value ≤ 0.10
- PEAD와 상관관계 ≤ 0.5

**예상 소요**: 1일

---

#### Phase 4: SUE 기반 PEAD v2 구현

**목표**: 시그널 품질 개선

**방법**:
1. SF1에서 Analyst Consensus 추출
2. SUE 계산: `(actual - consensus) / std(surprise)`
3. 이벤트 테이블 재구축
4. PEAD v1과 비교

**예상 효과**:
- Gross Incremental Sharpe: 0.07 → **0.3**
- Val p-value: 0.03 → **0.01**

**예상 소요**: 2-3일

---

#### Phase 5: Multi-Signal Ensemble

**목표**: 앙상블로 안정성 증가

**방법**:
1. PEAD + Buyback 2-signal ensemble
2. 최적 가중치 탐색 (Grid Search)
3. 상관관계 분석
4. 백테스트

**예상 효과**:
- Incremental Sharpe: 0.2 → **0.4**
- MDD 개선: -3%p → **-2%p**

**예상 소요**: 2-3일

---

## Part 3: 성공 기준 및 의사결정 트리

### 3.1 Phase별 성공 기준

#### Phase 1: ARES7 Base Weight 확보
- ✅ **성공**: weight matrix CSV 생성 완료
- ❌ **실패**: 2일 내 추출 불가 → Equal-Weight로 계속 진행

---

#### Phase 2: PEAD 파라미터 최적화

**성공 기준** (ARES7 Base 기준):
- ✅ **강력**: Net Incremental Sharpe ≥ 0.3
- ✅ **중간**: 0.1 ≤ Net Incremental Sharpe < 0.3
- ⚠️ **약함**: 0 ≤ Net Incremental Sharpe < 0.1
- ❌ **실패**: Net Incremental Sharpe < 0

**의사결정**:
- **강력** → Phase 3 진행 (Buyback 추가)
- **중간** → Phase 4 진행 (SUE 개선)
- **약함** → Phase 4 진행 (SUE 개선) + Budget 축소
- **실패** → PEAD 포기, Buyback으로 전환

---

#### Phase 3: Buyback 알파 분석

**성공 기준**:
- ✅ **강력**: Test Gross Sharpe ≥ 0.5, p ≤ 0.05
- ✅ **중간**: Test Gross Sharpe ≥ 0.3, p ≤ 0.10
- ⚠️ **약함**: Test Gross Sharpe ≥ 0.1, p ≤ 0.20
- ❌ **실패**: Test Gross Sharpe < 0.1 or p > 0.20

**의사결정**:
- **강력** → Phase 5 진행 (Ensemble)
- **중간** → Phase 5 진행 (Ensemble, 낮은 가중치)
- **약함** → Buyback 단독 사용 불가, PEAD만 사용
- **실패** → Buyback 포기

---

#### Phase 4: SUE 기반 PEAD v2

**성공 기준**:
- ✅ **성공**: v2 Gross Sharpe > v1 Gross Sharpe + 0.1
- ⚠️ **중립**: v2 Gross Sharpe ≈ v1 Gross Sharpe (±0.05)
- ❌ **실패**: v2 Gross Sharpe < v1 Gross Sharpe - 0.05

**의사결정**:
- **성공** → v2 사용, Phase 5 진행
- **중립** → v1 사용, Phase 5 진행
- **실패** → v1 사용, SUE 포기

---

#### Phase 5: Multi-Signal Ensemble

**성공 기준** (최종):
- ✅ **프로덕션 준비**: Net Incremental Sharpe ≥ 0.3, MDD ≤ +3%p
- ✅ **실험 단계**: 0.2 ≤ Net Incremental Sharpe < 0.3
- ⚠️ **관찰 대상**: 0.1 ≤ Net Incremental Sharpe < 0.2
- ❌ **포기**: Net Incremental Sharpe < 0.1

**의사결정**:
- **프로덕션 준비** → ARES8 배포
- **실험 단계** → 추가 최적화 (Fee, Horizon)
- **관찰 대상** → Paper trading 6개월
- **포기** → 이벤트 기반 알파 전략 중단

---

### 3.2 최종 목표 시스템 스펙

#### ARES8 v1.0 (Target)

**Base**:
- ARES7 weight matrix (팩터 최적화)

**Overlay**:
- PEAD (SUE 기반): Budget 2%, Horizon 15d
- Buyback: Budget 2%, Horizon 20d
- 총 Overlay Budget: **4%**

**예상 성과**:
- Base Sharpe: 0.90
- Overlay Incremental Sharpe: **0.30** (Net)
- **Combined Sharpe: 1.20**
- MDD: -33% → **-35%** (+2%p)
- 연간 수익률: 15.4% → **16.5%** (+1.1%p)

**거래비용**:
- 연간 Turnover: ~150%
- 연간 거래비용: ~0.15%
- **거래비용 < Overlay 알파** (0.15% < 0.40%)

---

## Part 4: 리스크 관리

### 4.1 주요 리스크

#### Risk 1: ARES7 Base Weight 부재
- **확률**: 30%
- **영향**: 높음
- **완화**: Equal-Weight로 계속 진행, 성능 저하 감수

#### Risk 2: PEAD 알파 소멸
- **확률**: 20%
- **영향**: 높음
- **완화**: Buyback으로 전환, 또는 이벤트 전략 포기

#### Risk 3: 거래비용 과소평가
- **확률**: 40%
- **영향**: 중간
- **완화**: Fee 0.1% → 0.15%로 재측정

#### Risk 4: Overfitting
- **확률**: 50%
- **영향**: 높음
- **완화**: Walk-Forward Analysis, Out-of-Sample 검증

---

### 4.2 모니터링 지표

#### 일별 모니터링
- Overlay 수익률
- Turnover
- 거래비용

#### 주별 모니터링
- Incremental Sharpe (Rolling 20d)
- MDD
- 팩터 노출 변화

#### 월별 모니터링
- Train/Val/Test 성능 비교
- 시장 체제별 성능
- 이벤트 분포 변화

---

## Part 5: 타임라인

### Week 1: Foundation
- **Day 1-2**: ARES7 Base Weight 확보
- **Day 3-4**: PEAD 파라미터 최적화 (Grid Search)
- **Day 5**: Buyback 이벤트 테이블 생성 완료
- **Day 6-7**: Buyback 알파 분석

### Week 2: Enhancement
- **Day 8-10**: SUE 기반 PEAD v2 구현
- **Day 11-12**: PEAD v1 vs v2 비교
- **Day 13-14**: Multi-Signal Ensemble 구현

### Week 3: Validation
- **Day 15-16**: Walk-Forward Analysis
- **Day 17-18**: Out-of-Sample 검증
- **Day 19-20**: 최종 백테스트
- **Day 21**: 결과 보고서 작성

### Week 4: Deployment
- **Day 22-23**: Paper Trading 준비
- **Day 24-25**: 모니터링 시스템 구축
- **Day 26-28**: ARES8 v1.0 배포

---

## Part 6: 핵심 인사이트

### 6.1 왜 지금까지 실패했는가?

1. **거래비용 과소평가**
   - PEAD 알파 0.04% << 거래비용 0.62%
   - Overlay Budget 10% → 5%로 축소했지만 여전히 과다

2. **Equal-Weight Base의 한계**
   - 팩터 노출 불명확
   - PEAD 시그널과 상호작용 복잡

3. **시그널 품질 부족**
   - EPS Surprise만 사용
   - Standardization 부재
   - 다차원 정보 미활용

---

### 6.2 성공을 위한 핵심 요소

#### 1. **ARES7 Base Weight** (최우선)
- 팩터 중립성 확보
- Overlay 효과 명확화

#### 2. **거래비용 최소화**
- Horizon 연장 (15~20d)
- Budget 축소 (2~3%)
- Fee Rate 재측정 (0.05%)

#### 3. **시그널 품질 개선**
- SUE 사용
- 분기 실적만 포함
- SF1 Full Data 활용

#### 4. **앙상블 전략**
- PEAD + Buyback
- 상관관계 낮은 시그널
- 안정성 증가

---

### 6.3 현실적 기대치

#### Pessimistic Case (확률 30%)
- Net Incremental Sharpe: 0.1
- 연간 초과수익: +0.2%
- **판단**: 실전 사용 불가, 연구 중단

#### Base Case (확률 50%)
- Net Incremental Sharpe: 0.2~0.3
- 연간 초과수익: +0.5~1.0%
- **판단**: Paper Trading 6개월 후 재평가

#### Optimistic Case (확률 20%)
- Net Incremental Sharpe: 0.3~0.5
- 연간 초과수익: +1.0~1.5%
- **판단**: 즉시 프로덕션 배포

---

## Part 7: 최종 권장사항

### 7.1 즉시 실행 (This Week)

1. **ARES7 Base Weight 확보** (최우선)
2. **PEAD Grid Search** (36개 조합)
3. **Buyback 알파 분석** (이벤트 테이블 생성 완료 대기 중)

### 7.2 단기 실행 (Next 2 Weeks)

4. **SUE 기반 PEAD v2 구현**
5. **Multi-Signal Ensemble**
6. **Walk-Forward Analysis**

### 7.3 중기 실행 (Next Month)

7. **Paper Trading 시작**
8. **모니터링 시스템 구축**
9. **ARES8 v1.0 배포 준비**

---

## Conclusion

**지속적인 알파와 높은 샤프니스를 달성하기 위한 핵심**:

1. ✅ **팩터 중립성 확보** (ARES7 Base Weight)
2. ✅ **거래비용 최소화** (Horizon 연장, Budget 축소, Fee 재측정)
3. ✅ **시그널 품질 개선** (SUE, 분기 실적, SF1 Full Data)
4. ✅ **앙상블 전략** (PEAD + Buyback + ...)

**현실적 목표**:
- Net Incremental Sharpe: **0.2~0.3**
- 연간 초과수익: **+0.5~1.0%**
- Combined Sharpe: **1.0~1.2**

**다음 단계**:
1. ARES7 Base Weight 확보
2. PEAD Grid Search 실행
3. Buyback 알파 분석 완료

---

**"The devil is in the details, but the alpha is in the execution."**
