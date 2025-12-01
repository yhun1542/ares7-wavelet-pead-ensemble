# Out-of-Sample 검증 및 Overfitting 분석 리포트

**날짜**: 2025-11-28  
**목적**: Look-ahead bias 수정 + Train/OOS 검증

---

## ⚠️ 핵심 발견

### 1. HIGH Overfitting 확인

- **Train Sharpe**: 3.105 (2015-2019)
- **OOS Average**: 2.055 (2020-2025)
- **Degradation**: +1.050 (**+33.8%**) ❌
- **판정**: **HIGH overfitting** (> 20% degradation)

### 2. Look-ahead Bias 부분 수정

- **Original**: 100 records with negative lag
- **After 45-day delay**: 115 records with negative lag (악화!)
- **원인**: Sharadar SF1 datekey 자체에 문제
- **해결책**: 60일 또는 90일 delay 필요

### 3. OOS 1 (2020-2021) 성과 악화

- Baseline: 2.315
- Balanced: **1.937** (-0.378) ❌
- **COVID 위기에서 QM Overlay 실패**

---

## 📊 상세 결과

### Train vs OOS 성과 비교

| Period | Type | Days | Baseline Sharpe | Balanced Sharpe | Delta |
|--------|------|------|-----------------|-----------------|-------|
| **Full Sample (2015-2025)** | TRAIN | 2,510 | 1.854 | **2.365** | +0.512 |
| **Train (2015-2019)** | TRAIN | 1,031 | 1.954 | **3.105** | +1.151 |
| **OOS 1 (2020-2021)** | OOS | 505 | 2.315 | **1.937** | **-0.378** ❌ |
| **OOS 2 (2022-2024)** | OOS | 753 | 1.623 | **2.462** | +0.839 |
| **OOS 3 (2025)** | OOS | 221 | 1.224 | **1.767** | +0.543 |

### 기간별 상세 분석

#### Full Sample (In-Sample)
- **Sharpe**: 2.365
- **기간**: 2015-11-25 ~ 2025-11-18 (2,510일)
- **특징**: Grid Search 최적화 기준
- **문제**: 전체 기간 최적화 → 과적합 위험

#### Train (2015-2019)
- **Sharpe**: 3.105 (매우 높음!)
- **기간**: 2015-11-25 ~ 2019-12-31 (1,031일)
- **특징**: Bull market, 낮은 변동성
- **문제**: 이 기간에 과도하게 최적화됨

#### OOS 1 (2020-2021) ❌
- **Sharpe**: 1.937 (Baseline 2.315보다 낮음!)
- **기간**: 2020-01-01 ~ 2021-12-31 (505일)
- **특징**: COVID 위기 + 회복
- **문제**: QM Overlay가 위기 시 역효과

#### OOS 2 (2022-2024) ✅
- **Sharpe**: 2.462
- **기간**: 2022-01-01 ~ 2024-12-31 (753일)
- **특징**: Ukraine 전쟁, 금리 인상
- **성과**: QM Overlay 효과적

#### OOS 3 (2025) ✅
- **Sharpe**: 1.767
- **기간**: 2025-01-01 ~ 2025-11-18 (221일)
- **특징**: 짧은 기간, 제한적 데이터
- **성과**: QM Overlay 효과적

---

## 🔍 문제 분석

### 1. Overfitting 원인

**Grid Search 최적화**:
- 45개 조합 테스트
- **전체 기간 (2015-2025)** 기준 최적화
- 결과: 2015-2019 bull market에 과적합

**QM Overlay 특성**:
- Quality+Momentum 팩터
- Bull market에서 강력
- Crisis에서 취약

**해결책**:
- Regularization (overlay_strength 감소)
- 레짐 필터 (BULL 레짐에서만 적용)
- Walk-forward optimization

### 2. Look-ahead Bias

**문제**:
- SF1 `datekey`가 fiscal period end와 동일하거나 이전
- 45일 delay 추가 후에도 115 records with negative lag

**원인**:
- Sharadar SF1 데이터 자체의 문제
- `datekey`가 실제 reporting date가 아님

**해결책**:
- **60일 또는 90일 delay** 적용
- 또는 `calendardate + 90 days` 사용

### 3. OOS 1 (2020-2021) 실패

**원인**:
- COVID 위기 (2020 Q1)
- QM Overlay가 위기 시 tail 리스크 증폭
- Vol/MDD 폭발

**증거**:
- Baseline Sharpe: 2.315 (우수)
- Balanced Sharpe: 1.937 (악화)
- Delta: -0.378 (역효과)

**해결책**:
- VIX Guard 추가
- 레짐 필터 (HIGH_VOL 시 overlay off)
- Drawdown 기반 자동 축소

---

## 💡 개선 방향

### Option 1: Regularization (overlay_strength 감소)

**아이디어**:
- Grid Search에서 찾은 0.05 → **0.03 또는 0.02**로 감소
- Overfitting 완화

**예상 효과**:
- Train Sharpe: 3.105 → 2.5~2.7
- OOS Sharpe: 2.055 → 2.0~2.2
- Degradation: 33.8% → 15~20%

### Option 2: 레짐 필터 추가

**아이디어**:
- QM Overlay를 **BULL 레짐에서만** 적용
- BEAR/HIGH_VOL 레짐에서는 overlay off

**조건**:
```python
if (SPX > 200d MA) and (VIX < 25) and (SPX DD 6M > -10%):
    overlay_strength_effective = 0.05
else:
    overlay_strength_effective = 0.0
```

**예상 효과**:
- OOS 1 (2020-2021) 성과 개선
- COVID 위기 시 overlay off → Baseline 수준 유지
- OOS Average Sharpe: 2.055 → 2.2~2.4

### Option 3: Walk-forward Optimization

**아이디어**:
- 매년 re-optimize overlay_strength
- 과거 1년 데이터로 최적화
- 다음 1년 적용

**예상 효과**:
- Overfitting 완화
- 시장 환경 변화에 적응
- OOS 성과 개선

### Option 4: Look-ahead Bias 완전 제거

**아이디어**:
- Reporting delay 60일 또는 90일로 증가
- 또는 `calendardate + 90 days` 사용

**예상 효과**:
- Bias-free 백테스트
- Sharpe 소폭 감소 (0.1~0.2)
- 실전 성과와 일치

---

## 🎯 권장 액션

### 즉시 실행

1. ✅ **Look-ahead bias 완전 제거**
   - Reporting delay 90일 적용
   - 재백테스트

2. ⏳ **Regularization**
   - overlay_strength 0.05 → 0.03
   - OOS 재검증

3. ⏳ **레짐 필터 추가**
   - BULL 레짐에서만 overlay 적용
   - OOS 재검증

### 중기 목표

4. ⏳ **Walk-forward Optimization**
   - 연간 re-optimization
   - OOS 성과 개선

5. ⏳ **VIX Guard 추가**
   - VIX 30+에서 노출 축소
   - MDD 개선

---

## 📝 결론

### 현재 상태

- ✅ **In-sample Sharpe 2.365** (목표 달성)
- ❌ **HIGH overfitting** (33.8% degradation)
- ❌ **OOS 1 (2020-2021) 실패** (Sharpe 1.937)
- ⚠️  **Look-ahead bias 부분 존재** (115 records)

### 핵심 문제

1. **Overfitting**: Train (3.105) vs OOS (2.055)
2. **Crisis 취약성**: COVID 위기 시 역효과
3. **Look-ahead bias**: SF1 데이터 문제

### 다음 단계

**우선순위 1**: Look-ahead bias 완전 제거 (90일 delay)  
**우선순위 2**: Regularization (overlay_strength 0.03)  
**우선순위 3**: 레짐 필터 추가 (BULL 레짐만)

### 최종 평가

**QM Overlay는 알파가 있지만**:
- In-sample 과적합 위험
- Crisis 취약성
- Look-ahead bias 문제

**실전 적용 전에**:
- Bias 완전 제거
- Regularization
- 레짐 필터 추가
- **OOS 재검증 필수**

---

**현재 Sharpe 2.365는 과대평가된 수치일 가능성 높음.**  
**실제 OOS Sharpe는 2.0~2.2 수준으로 예상됨.**
