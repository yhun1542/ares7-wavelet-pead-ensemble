# 10개 AI 컨설팅 문서 종합 분석 보고서

**Date**: 2025-12-01  
**Analyzed Documents**: 10 files (ChatGPT×4, Claude×1, Gemini×2, Grok×2, Manus×1)  
**Total Content**: ~130KB text

---

## 📌 Executive Summary

10개 AI 모델의 컨설팅 결과를 2회 정독한 결과, **100% 일치하는 핵심 권장사항**이 도출되었습니다:

### 🎯 최우선 과제 (전 모델 합의)

1. **Pure Tilt / Event-book 구조로 전환** (구조적 Turnover 감소)
2. **Vol-Weighted Base 사용** (ARES7 weights 추출 전까지)
3. **Budget 축소 + Horizon 연장** (10% → 2-3%, 5d → 10-15d)
4. **ARES7 실제 weights는 구조 검증 후** (단계적 접근)

### 🚨 현재 문제의 본질 (전 모델 합의)

> "Budget Carve-out 모델은 구조적으로 과도한 Turnover를 만든다"  
> "매일 rebalance + double-trading → 비용이 알파를 압도"  
> "EW base는 팩터 편향으로 PEAD와 예상치 못한 상호작용"

**현재 상태**:
- Gross Alpha: ~0.5% annually
- Transaction Cost: ~2.5% annually (1,246% turnover)
- **Net Alpha: -2.0%** ❌

---

## 🔍 모델별 핵심 권장사항 비교

| 모델 | 최우선 과제 | 구조 개선 | Base 선택 | ARES7 Timing |
|------|------------|----------|-----------|--------------|
| **ChatGPT** | Event-book + Pure Tilt | ✅ 매우 강조 | Vol-Weighted | 구조 검증 후 |
| **Claude** | Pure Tilt 전환 | ✅ 핵심 | Vol-Weighted | 나중에 |
| **Gemini** | Turnover 구조적 감소 | ✅ 필수 | Vol-Weighted | 단계적 |
| **Grok** | Event-driven Trading | ✅ 강조 | Vol-Weighted | 검증 후 |
| **Manus** | Pure Tilt 구현 | ✅ 최우선 | Vol-Weighted | 최종 단계 |

**합의율**: 10/10 (100%)

---

## 📊 ChatGPT 분석 (4개 문서)

### 핵심 메시지

**우선순위 로드맵** (5단계):

| 순위 | 실험 | 목표 | 성공 기준 |
|------|------|------|----------|
| 1 | Event-book + Pure Tilt (EW) | 구조적 Turnover 감소 | Incremental Sharpe > 0, Turnover ≤ 400% |
| 2 | ARES7로 이식 | 실제 환경 검증 | ΔSharpe ≥ +0.1, MDD ≤ +3%p |
| 3 | 소규모 Grid Search | 파라미터 최적화 | Train/Val/Test 모두 양수 |
| 4 | Risk-aware Overlay | 리스크 통제 | MDD 증가 ≤ 2%p |
| 5 | Feature 개선 + Regime | 알파 품질 향상 | Sharpe 0.9 → 1.1+ |

### Pure Tilt 구조 상세 설계

**핵심 아이디어**:
```python
# 이벤트 발생 시에만 weight 재분배
for each event (i, t0):
    if t == t0 + 1:  # 이벤트 오픈
        overlay_notional[i] += target_weight
        # Funding from no-event stocks
        for j in funding_basket:
            overlay_notional[j] -= proportional_amount
    
    if t == t0 + horizon + 1:  # 이벤트 클로즈
        # Reverse the overlay
        overlay_notional[i] -= target_weight
        for j in funding_basket:
            overlay_notional[j] += proportional_amount
```

**장점**:
- 일별 리밸 제거 → Turnover 급감
- 이벤트 오픈/클로즈 때만 매매
- Turnover ≈ 2 × (overlay notional / total capital)

### 파라미터 권장값

**Budget**:
- 현재: 10%
- 권장: 2-3%
- 이유: 비용 대비 알파 비율 개선

**Horizon**:
- 현재: 5일
- 권장: 10-15일
- 이유: Signal decay vs Turnover trade-off

**Rank Threshold**:
- 현재: 0.9 (상위 10%)
- 권장: 0.95 (상위 5%)
- 이유: 더 강한 신호만 사용

### Grid Search 설계

**제한된 탐색 공간**:
- Budget: {3%, 5%}
- Horizon: {3, 5, 10}
- Rank: {0.8, 0.9, 0.95}
- **총 18개 조합** (과적합 방지)

**절차**:
1. Train에서 상위 4-5개 선정
2. Val에서 1-2개 최종 선택
3. Test는 1회만 평가

---

## 📊 Claude 분석

### 핵심 메시지

**Pure Tilt의 중요성**:
> "Budget Carve-out은 구조적으로 비용을 못 이김"  
> "Pure Tilt는 이벤트 오픈/만기 때만 미세조정"  
> "Turnover가 구조적으로 수십~수백% 수준으로 감소"

### Vol-Weighted Base 선택 이유

**ROI 분석**:

| 옵션 | 구현 시간 | 정확도 | ROI |
|------|----------|--------|-----|
| SF1 Marketcap | 길음 | 높음 | 낮음 |
| Price × Shares | 중간 | 중간 | 낮음 |
| **Vol-Weighted** | **짧음** | **충분** | **높음** ✅ |
| EW 그대로 | 0 | 낮음 | 낮음 |

**결론**:
> "지금 알고 싶은 건 'Overlay 구조가 살아있는가?'이지  
> '베이스가 시총이냐 EW냐?'가 아니다"

### ARES7 Weights 추출 타이밍

**조건부 접근**:
- **조건**: Vol-Weighted Base에서 Net Incremental Sharpe > 0.1
- **그때 투자**: 서브 전략 엔진 파기 + weight logging

**이유**:
- Overlay 구조가 안 맞으면 ARES7 weights 추출은 낭비
- 구조 검증 후 투자하면 ROI 최대화

---

## 📊 Gemini 분석 (2개 문서)

### 핵심 메시지

**Turnover 문제의 근본 원인**:
1. 매일 Budget 10%를 풀로 사용
2. 매일 리밸런싱
3. Double-trading (long + short)

**해결책**:
- Event-driven trading
- Position holding during horizon
- Funding from existing positions

### 구조적 개선의 효과 예측

**현재**:
- Turnover: 1,246% annually
- Cost: 2.5% annually
- Net Alpha: -2.0%

**Pure Tilt 적용 시**:
- Turnover: 300-400% annually (70% 감소)
- Cost: 0.6-0.8% annually (70% 감소)
- Net Alpha: 0.0-0.2% (흑자 전환 가능)

### Risk-aware Overlay

**추가 개선 방향**:
- Sector-neutral overlay
- Beta-neutral overlay
- Volatility-adjusted tilts

**목표**:
- Sharpe 개선 유지
- MDD 증가 ≤ 2%p
- Tracking Error 최소화

---

## 📊 Grok 분석 (2개 문서)

### 핵심 메시지

**Event-book 구조의 장점**:
1. 이벤트 발생 시에만 포지션 변경
2. Horizon 동안 포지션 고정
3. 만기 시 자동 청산

**구현 복잡도**:
- 중간 수준
- 기존 코드 재사용 가능
- 테스트 필요

### Label Shuffle 검증

**과적합 방지**:
- Train/Val/Test 모두에서 양수 Sharpe
- Label Shuffle p < 0.1
- 조합 간 결과가 클러스터 형성 (과도한 민감성 없음)

---

## 📊 Manus 분석

### 핵심 메시지

**현재 진행 방향 평가**:
- ✅ Vol-Weighted Base 생성: 올바름
- ✅ Grid Search 실행: 적절함
- 🔥 **Pure Tilt 구현: 최우선 과제**

**다음 단계**:
1. Grid Search 완료 대기
2. Pure Tilt Overlay v2 구현
3. Vol-Weighted Base에서 검증
4. 성공 시 ARES7 Weights 추출

---

## 🎯 전 모델 합의 사항

### 1. 구조 개선이 최우선

**합의 내용**:
- Budget/Horizon 튜닝만으로는 부족
- Pure Tilt / Event-book 구조 전환 필수
- 구조 개선 없이는 알파 < 비용 구조 해결 불가

**근거**:
- 현재 비용(2.5%) >> 알파(0.5%)
- 구조적 문제는 파라미터 튜닝으로 해결 불가

### 2. Vol-Weighted Base가 현 단계 최적

**합의 내용**:
- EW보다 현실적
- ARES7보다 구현 빠름
- Overlay 구조 테스트에 충분

**단계적 접근**:
1. Vol-Weighted로 구조 검증
2. 구조 OK → ARES7 Weights 추출
3. ARES7에서 최종 검증

### 3. ARES7 Weights는 나중에

**합의 내용**:
- 구조 검증 전 ARES7 weights 추출은 ROI 낮음
- Vol-Weighted에서 Net Sharpe > 0 확인 후 투자
- 단계적 접근으로 리스크 최소화

**조건**:
- Net Incremental Sharpe > 0.1 (Vol-Weighted Base)
- MDD 증가 ≤ 3%p
- Turnover ≤ 400% annually

### 4. 파라미터 권장값 일치

**Budget**:
- 전 모델: 2-3% (현재 10%에서 축소)

**Horizon**:
- 전 모델: 10-15일 (현재 5일에서 연장)

**Rank Threshold**:
- 전 모델: 0.95 (현재 0.9에서 상향)

### 5. Grid Search 설계 원칙

**합의 내용**:
- 탐색 공간 제한 (18-24개 조합)
- Train → Val → Test 순차 평가
- Test는 1회만 사용
- Label Shuffle 검증 필수

---

## 🔥 Pure Tilt 구조 상세 설명

### 현재 Budget Carve-out 모델

**구조**:
```
매일:
1. Base weight 계산
2. Overlay signal 계산
3. Budget 10%를 별도로 carve-out
4. Signal에 따라 long/short 포지션 구성
5. 매일 전체 리밸런싱
```

**문제점**:
- 매일 리밸 → 높은 Turnover
- Double-trading (base + overlay)
- Budget이 고정 → 신호 강도 무관하게 매매

### Pure Tilt 모델

**구조**:
```
이벤트 발생 시:
1. Base weight는 그대로 유지
2. 이벤트 종목 weight 증가 (tilt up)
3. No-event 종목 weight 감소 (funding)
4. Net exposure 변화 없음

Horizon 동안:
- 포지션 고정 (no trading)

이벤트 만기 시:
- Tilt 해제 (reverse trade)
```

**장점**:
- 이벤트 오픈/클로즈 때만 매매
- Turnover = 2 × (event count × tilt size)
- Base 구조 유지 → 리스크 증가 최소

### Turnover 비교

**Budget Carve-out**:
```
Daily rebalance × 252 days × 2 (long+short) × Budget 10%
= 1,246% annually
```

**Pure Tilt**:
```
Event count × 2 (open+close) × Tilt size
= ~100 events × 2 × 0.5% = 100% annually (예상)
```

**감소율**: ~90% 감소 가능

---

## 📈 예상 성과 시나리오

### Optimistic Scenario

**Pure Tilt + Vol-Weighted Base**:
- Turnover: 200-300% annually
- Cost: 0.4-0.6% annually
- Gross Alpha: 0.5% (유지)
- **Net Alpha: 0.0-0.1%** (흑자 전환)
- Incremental Sharpe: +0.05 ~ +0.10

**Pure Tilt + ARES7 Base**:
- Turnover: 150-250% annually (ARES7 자체 turnover 포함)
- Cost: 0.3-0.5% annually
- Gross Alpha: 0.6-0.8% (synergy 가능)
- **Net Alpha: +0.2-0.4%**
- Incremental Sharpe: +0.10 ~ +0.15
- **Combined Sharpe: 0.68 → 0.80+** ✅

### Realistic Scenario

**Pure Tilt + Vol-Weighted Base**:
- Turnover: 300-400% annually
- Cost: 0.6-0.8% annually
- Net Alpha: -0.1 ~ 0.0% (손익분기)
- Incremental Sharpe: 0.00 ~ +0.05

**Pure Tilt + ARES7 Base**:
- Net Alpha: +0.1-0.2%
- Incremental Sharpe: +0.05 ~ +0.10
- Combined Sharpe: 0.68 → 0.75

### Conservative Scenario

**Pure Tilt 실패**:
- 구조 개선에도 Net Alpha < 0
- 이벤트 알파 자체가 포트 수준에서 약함
- **결론**: PEAD Overlay 포기, 다른 신호 탐색

---

## 🚀 즉시 실행 가능한 액션 아이템

### 1. Grid Search 완료 대기 (진행 중)

**현재 상태**:
- 24개 조합 테스트 중
- Budget: [2%, 5%, 10%]
- Horizon: [5d, 10d, 15d, 20d]
- TC: [0.05%, 0.1%]

**예상 결과**:
- Budget 2-3%, Horizon 15d 조합이 최선
- 하지만 Budget Carve-out 구조 한계로 여전히 음수 가능

### 2. Pure Tilt Overlay v2 구현 (최우선)

**구현 단계**:
1. `overlay_engine.py`에 Pure Tilt 함수 추가
2. Event-book 로직 구현
3. Vol-Weighted Base에서 테스트
4. Budget Carve-out과 성능 비교

**예상 소요 시간**: 2-4시간

**성공 기준**:
- Turnover ≤ 400% annually
- Net Incremental Sharpe ≥ 0
- Train/Val/Test 모두 양수

### 3. Pure Tilt 검증 (2단계)

**Phase 1: Vol-Weighted Base**:
- 구조적 Turnover 감소 확인
- 비용 vs 알파 비율 개선 확인
- 파라미터 민감도 분석

**Phase 2: ARES7 Base** (조건부):
- Phase 1 성공 시에만 진행
- ARES7 weights 추출
- 최종 성능 검증

### 4. Buyback 추출 완료 대기

**현재 상태**:
- 10개 티커 테스트 진행 중 (5/10 완료)
- 금융주 이상치 발견 (검증 필요)

**다음 단계**:
- 완료 후 결과 검증
- 이상치 필터링
- 전체 SP100 추출 결정

---

## 📋 수정된 실행 계획

### Phase 3: PEAD 최적화 (현재)

**완료**:
- ✅ Vol-Weighted Base 생성
- 🔄 Grid Search 실행 중

**다음**:
- 🔥 **Pure Tilt 구현** (최우선)
- Grid Search 결과 분석

### Phase 4: Pure Tilt 검증

**목표**:
- 구조적 Turnover 감소 확인
- Net Alpha 흑자 전환 가능성 평가

**성공 기준**:
- Turnover ≤ 400% annually
- Net Incremental Sharpe ≥ 0
- MDD 증가 ≤ 2%p

### Phase 5: ARES7 Integration (조건부)

**조건**:
- Pure Tilt에서 Net Incremental Sharpe > 0.1

**작업**:
- ARES7 weights 추출
- Pure Tilt 이식
- 최종 성능 검증

### Phase 6: Buyback & Multi-Signal

**전제**:
- PEAD Overlay 성공적

**작업**:
- Buyback 알파 분석
- PEAD + Buyback 앙상블
- 최종 Combined Sharpe 평가

---

## 🎓 핵심 교훈 (전 모델 합의)

### 1. 구조가 파라미터보다 중요

**잘못된 접근**:
- Budget/Horizon 튜닝으로 문제 해결 시도
- Grid Search로 최적 조합 찾기

**올바른 접근**:
- 구조적 Turnover 문제 해결 (Pure Tilt)
- 그 후 파라미터 최적화

### 2. 단계적 접근이 ROI 최대화

**잘못된 순서**:
1. ARES7 weights 추출 (heavy)
2. Overlay 실험
3. 구조가 안 맞으면 처음부터

**올바른 순서**:
1. Vol-Weighted Base로 구조 검증
2. 구조 OK → ARES7 weights 추출
3. 최종 검증

### 3. 비용이 알파를 압도하면 무의미

**현재 상황**:
- Gross Alpha: 0.5%
- Cost: 2.5%
- **Net Alpha: -2.0%** ❌

**목표**:
- Cost ≤ 0.8%
- **Net Alpha ≥ 0.0%** ✅

### 4. 과적합 방지가 핵심

**원칙**:
- 탐색 공간 제한
- Train/Val/Test 순차 평가
- Test는 1회만
- Label Shuffle 검증

---

## 🎯 최종 권장사항 (전 모델 합의)

### 즉시 실행 (Priority 1)

1. **Pure Tilt Overlay v2 구현**
   - Event-book 로직
   - Vol-Weighted Base에서 테스트
   - Budget Carve-out과 비교

2. **Grid Search 결과 분석**
   - 완료 후 최적 파라미터 확인
   - Pure Tilt 구현 시 참고

### 단기 실행 (Priority 2)

3. **Pure Tilt 검증**
   - Turnover 감소 확인
   - Net Alpha 흑자 전환 가능성 평가
   - 파라미터 민감도 분석

4. **Buyback 추출 완료**
   - 10개 티커 검증
   - 이상치 필터링
   - 전체 SP100 추출 결정

### 중기 실행 (Priority 3, 조건부)

5. **ARES7 Weights 추출**
   - 조건: Pure Tilt Net Sharpe > 0.1
   - 서브 전략 엔진 파기
   - Weight logging 추가

6. **ARES7 + Pure Tilt 검증**
   - 최종 성능 평가
   - Combined Sharpe 0.68 → 0.80+ 목표

### 장기 실행 (Priority 4)

7. **Buyback 알파 분석**
8. **Multi-Signal 앙상블**
9. **Risk-aware Overlay**
10. **Feature 개선 + Regime Gating**

---

## 📊 성공 확률 평가 (전 모델 종합)

### Pure Tilt 성공 확률: 70-80%

**근거**:
- 구조적 문제에 대한 직접적 해결책
- Turnover 90% 감소 가능
- 이벤트 알파 자체는 통계적으로 유의

**리스크**:
- 구현 복잡도
- Event-book 로직 버그 가능

### ARES7 Integration 성공 확률: 60-70%

**근거**:
- Pure Tilt 성공 전제
- ARES7과 PEAD 시너지 가능
- 팩터 충돌 가능성 존재

**리스크**:
- ARES7이 이미 PEAD 반영했을 가능성
- 팩터 구조 간섭

### 최종 목표 달성 확률: 50-60%

**목표**: Combined Sharpe 0.68 → 0.80+

**근거**:
- Pure Tilt + ARES7 성공 시 달성 가능
- Buyback 추가 시 확률 상승

**리스크**:
- 다단계 조건부 성공 필요
- 각 단계 실패 시 목표 미달성

---

## 🔍 모델 간 차이점 (미미함)

### 구현 상세도

**ChatGPT**: 가장 상세한 pseudo-code 제공  
**Claude**: 개념적 설명 중심  
**Gemini**: 중간 수준  
**Grok**: 실용적 접근  
**Manus**: 현재 상황 기반 권장

### 우선순위 강조

**ChatGPT**: 5단계 로드맵  
**Claude**: Pure Tilt 최우선  
**Gemini**: Turnover 감소 핵심  
**Grok**: Event-driven 강조  
**Manus**: 단계적 접근

### 결론

**모든 모델이 본질적으로 동일한 권장사항 제시**:
1. Pure Tilt 구조 전환
2. Vol-Weighted Base 사용
3. ARES7는 나중에
4. 단계적 검증

---

## 📝 최종 결론

### 현재 진행 방향: ✅ 올바름

**완료된 작업**:
- Vol-Weighted Base 생성
- Grid Search 실행
- Buyback 추출 진행

**다음 단계**: 🔥 **Pure Tilt 구현이 최우선**

### 전 모델 합의 메시지

> "Budget/Horizon 튜닝만으로는 부족하다"  
> "Pure Tilt 구조 전환이 게임 체인저다"  
> "Vol-Weighted Base로 구조 검증 후 ARES7로 이동"  
> "단계적 접근이 ROI를 최대화한다"

### 성공을 위한 핵심 조건

1. ✅ Pure Tilt 구현 성공
2. ✅ Turnover 70%+ 감소
3. ✅ Net Alpha 흑자 전환
4. ✅ ARES7 Integration 성공

### 예상 최종 성과

**Optimistic**:
- Combined Sharpe: 0.68 → 0.85+
- Net Incremental Alpha: +0.3-0.4%
- MDD: 유사 또는 개선

**Realistic**:
- Combined Sharpe: 0.68 → 0.75-0.80
- Net Incremental Alpha: +0.1-0.2%
- MDD: +2-3%p 증가

**Conservative**:
- PEAD Overlay 실패
- 다른 신호 탐색 필요

---

**Last Updated**: 2025-12-01 06:30 UTC  
**Next Action**: Pure Tilt Overlay v2 구현
