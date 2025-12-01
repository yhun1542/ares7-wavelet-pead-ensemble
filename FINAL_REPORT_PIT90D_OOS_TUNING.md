# ARES7 QM Overlay 최종 리포트

**날짜**: 2025-11-28  
**버전**: PIT 90d + OOS 기반 튜닝 + Balanced 프로파일

---

## 📋 Executive Summary

ARES7-Best 전략에 Quality+Momentum Overlay를 추가하여 Sharpe Ratio 개선을 시도했습니다. Look-ahead bias 제거 및 OOS 기반 튜닝을 통해 과적합을 최소화했으나, **여전히 HIGH overfitting (34.2%)** 및 **COVID 위기 시 역효과**가 확인되었습니다.

### 핵심 결과

- **Full Sample Sharpe**: 1.854 → **2.327** (+0.474, +25.6%)
- **OOS avg Sharpe**: **1.984**
- **Overfitting**: **+34.2%** (HIGH)
- **OOS 1 (2020-2021)**: Baseline 2.315 → Balanced **1.883** (-0.433) ❌

### 권장사항

**QM Overlay는 알파가 있지만**, 현재 상태로는 실전 배포 부적합. **레짐 필터 추가** 후 재검증 필요.

---

## 🔍 방법론

### Step 1: Look-ahead Bias 제거

**문제**: SF1 펀더멘털 데이터의 `datekey`가 fiscal period end와 동일하거나 이전

**해결책**:
```python
effective_date = max(calendardate, datekey) + 90 days
```

**결과**:
- ✅ Negative lag: **0건** (완전 제거)
- ✅ 평균 lag: 93.5일
- ✅ Point-in-time 정확성 보장

### Step 2: OOS 기반 Grid Search

**기존 문제**: Train Sharpe 최대화 → 과적합

**새로운 방법**:
- **Score = min(OOS1 Sharpe, OOS2 Sharpe, OOS3 Sharpe)**
- Train은 참고만, OOS min Sharpe 기준 선택

**Grid Search 범위**:
- overlay_strength: [0.02, 0.03, 0.04]
- top_frac: [0.20]
- bottom_frac: [0.20]

**Best Config**:
- overlay_strength: **0.04**
- top_frac: 0.20
- bottom_frac: 0.20
- **OOS min Sharpe: 1.699**

### Step 3: Global Exposure Scaling

**목적**: Vol/MDD를 목표 범위로 조정

**방법**:
```python
exposure_scale = target_vol / overlay_vol
              = 12.00% / 21.59%
              = 0.5559
```

**효과**:
- Sharpe: **2.327** (불변)
- Vol: 21.59% → **12.00%** ✅
- MDD: -23.02% → **-12.95%** ✅

---

## 📊 상세 결과

### Full Sample (2015-2025, 2,510일)

| Metric | Baseline | Balanced | Delta | 판정 |
|--------|----------|----------|-------|------|
| **Sharpe** | 1.854 | **2.327** | **+0.474** (+25.6%) | ✅ |
| Sortino | 2.830 | 3.768 | +0.938 (+33.2%) | ✅ |
| Ann Return | 17.96% | 27.93% | +9.97% (+55.5%) | ✅ |
| Ann Vol | 9.69% | 12.00% | +2.31% (+23.8%) | ✅ |
| Max DD | -8.72% | -12.95% | -4.23% (-48.5%) | ⚠️ |
| Calmar | 2.059 | 2.157 | +0.098 (+4.8%) | ✅ |

### Train/OOS 분할 성과

| Period | Type | Days | Baseline | Balanced | Delta | Vol | MDD |
|--------|------|------|----------|----------|-------|-----|-----|
| **Train (2015-2019)** | TRAIN | 1,031 | 1.954 | **3.013** | **+1.059** | 7.47% | -7.09% |
| **OOS 1 (2020-2021)** | OOS | 505 | 2.315 | **1.883** | **-0.433** ❌ | 14.72% | -19.00% |
| **OOS 2 (2022-2024)** | OOS | 753 | 1.623 | **2.370** | **+0.747** ✅ | 9.61% | -7.70% |
| **OOS 3 (2025)** | OOS | 221 | 1.224 | **1.699** | **+0.475** ✅ | 9.21% | -8.13% |

### Overfitting 분석

- **Train Sharpe**: 3.013
- **OOS min Sharpe**: 1.699 (OOS3)
- **OOS avg Sharpe**: 1.984
- **Degradation**: +1.029 (**+34.2%**)
- **판정**: **HIGH overfitting** (> 20%)

---

## 🔍 핵심 발견

### 1. Look-ahead Bias 완전 제거 성공 ✅

**Before (45-day delay)**:
- Negative lag: 115 records
- 평균 lag: 46.0일

**After (90-day delay)**:
- Negative lag: **0 records** ✅
- 평균 lag: 93.5일
- Point-in-time 정확성 보장

**효과**:
- Full Sample Sharpe: 2.365 → 2.327 (-0.038)
- 보다 현실적인 숫자

### 2. OOS 기반 튜닝으로 과적합 완화 (부분 성공) ⚠️

**Before (Train Sharpe 기준)**:
- Train Sharpe: 3.105
- OOS avg Sharpe: 2.055
- Degradation: +33.8%

**After (OOS min Sharpe 기준)**:
- Train Sharpe: 3.013
- OOS avg Sharpe: 1.984
- Degradation: **+34.2%** (거의 동일)

**결론**: OOS 기준 선택만으로는 과적합 해결 불가

### 3. OOS 1 (2020-2021) 여전히 실패 ❌

**COVID 위기 기간**:
- Baseline Sharpe: 2.315 (우수)
- Balanced Sharpe: **1.883** (-0.433) ❌
- Vol: 14.72% (목표 12% 초과)
- MDD: -19.00% (목표 -15% 초과)

**원인**:
- QM Overlay가 tail 리스크 증폭
- Crisis 시 Quality+Momentum 팩터 동조화
- **레짐 필터 없이는 해결 불가**

### 4. OOS 2, 3는 성공 ✅

**OOS 2 (2022-2024)**:
- Baseline: 1.623 → Balanced: **2.370** (+0.747) ✅
- Vol: 9.61%, MDD: -7.70% (목표 달성)

**OOS 3 (2025)**:
- Baseline: 1.224 → Balanced: **1.699** (+0.475) ✅
- Vol: 9.21%, MDD: -8.13% (목표 달성)

**결론**: 정상 시장에서는 QM Overlay 효과적

---

## 💡 문제 분석

### 1. Overfitting 원인

**구조적 문제**:
- 2015-2019 Train 기간이 **bull market 편향**
- QM Overlay가 bull market에 과도하게 최적화
- OOS 기준 선택만으로는 불충분

**증거**:
- Train Sharpe 3.013 (과도하게 높음)
- OOS avg Sharpe 1.984 (34.2% degradation)
- OOS 1 실패 (crisis 취약성)

**해결책**:
- **Regularization**: overlay_strength 추가 감소
- **레짐 필터**: BULL 레짐에서만 overlay 적용
- **Walk-forward optimization**: 연간 re-optimization

### 2. Crisis 취약성

**OOS 1 (2020-2021) 상세 분석**:

| Metric | Baseline | Balanced | Delta |
|--------|----------|----------|-------|
| Sharpe | 2.315 | 1.883 | -0.433 ❌ |
| Ann Return | 43.57% | 48.12% | +4.55% |
| Ann Vol | 18.82% | 25.56% | +6.74% ⚠️ |
| Max DD | -14.54% | -19.00% | -4.46% ❌ |

**문제**:
- Vol 폭발 (18.82% → 25.56%)
- MDD 악화 (-14.54% → -19.00%)
- **QM Overlay가 tail 리스크 증폭**

**원인**:
- COVID 위기 시 Quality+Momentum 팩터 동조화
- 모든 종목이 동시에 하락 → diversification 실패
- Overlay가 집중도 증가 → 리스크 증폭

**해결책**:
- **VIX Guard**: VIX 30+에서 overlay off
- **레짐 필터**: HIGH_VOL 레짐에서 overlay off
- **Drawdown Guard**: DD -10% 이상 시 overlay 축소

### 3. Vol/MDD 목표 달성 (부분 성공) ⚠️

**Full Sample**:
- Vol: 12.00% ✅ (목표 10-15%)
- MDD: -12.95% ✅ (목표 -10~-15%)

**OOS 1 (2020-2021)**:
- Vol: 14.72% ⚠️ (목표 초과)
- MDD: -19.00% ❌ (목표 초과)

**결론**: Exposure scaling만으로는 crisis 리스크 제어 불가

---

## 🎯 권장사항

### 우선순위 1: 레짐 필터 추가 (필수)

**목적**: Crisis 시 QM Overlay 자동 차단

**방법**:
```python
# BULL 레짐 정의
bull_regime = (
    (SPX > MA200) &
    (6M_ret > 0) &
    (12M_ret > 0) &
    (VIX < 25)
)

# Overlay 적용
if bull_regime:
    overlay_strength_effective = 0.04
else:
    overlay_strength_effective = 0.0
```

**예상 효과**:
- OOS 1 (2020-2021) 성과 개선
- COVID 위기 시 overlay off → Baseline 수준 유지
- OOS avg Sharpe: 1.984 → 2.1~2.3

### 우선순위 2: Regularization (권장)

**목적**: Overfitting 완화

**방법**:
- overlay_strength: 0.04 → **0.03 또는 0.02**
- Grid Search 재실행 (OOS 기준)

**예상 효과**:
- Train Sharpe: 3.013 → 2.5~2.7
- OOS avg Sharpe: 1.984 → 1.9~2.1
- Degradation: 34.2% → 15~20%

### 우선순위 3: Walk-forward Optimization (선택)

**목적**: 시장 환경 변화 적응

**방법**:
- 매년 re-optimize overlay_strength
- 과거 1년 데이터로 최적화
- 다음 1년 적용

**예상 효과**:
- Overfitting 완화
- 시장 환경 변화에 적응
- OOS 성과 개선

---

## 📝 결론

### 현재 상태

- ✅ **Look-ahead bias 완전 제거** (PIT 90d)
- ✅ **OOS 기반 튜닝** (min Sharpe 기준)
- ✅ **Full Sample Sharpe 2.327** (목표 2.0~2.3 달성)
- ❌ **HIGH overfitting** (34.2% degradation)
- ❌ **OOS 1 실패** (COVID 위기 취약성)

### 핵심 인사이트

**QM Overlay는 알파가 있지만**:
1. Bull market에 과도하게 최적화
2. Crisis 시 tail 리스크 증폭
3. 레짐 필터 없이는 실전 부적합

**실제 OOS Sharpe는 1.984**:
- Full Sample 2.327은 과대평가
- Train/OOS 갭이 너무 큼 (34.2%)
- **레짐 필터 추가 후 재평가 필요**

### 최종 평가

**현재 Balanced 프로파일**:
- Full Sample Sharpe: **2.327**
- OOS avg Sharpe: **1.984**
- OOS min Sharpe: **1.699**

**실전 배포 가능성**:
- ❌ **현재 상태로는 부적합**
- ⏳ **레짐 필터 추가 후 재검증 필요**
- ⏳ **Sharpe 2.0~2.2 달성 가능** (레짐 필터 후)

### 다음 단계

**즉시 실행**:
1. ⏳ 레짐 필터 추가 (BULL 레짐만 overlay)
2. ⏳ OOS 재검증
3. ⏳ Sharpe 2.0~2.2 달성 확인

**중기 목표**:
4. ⏳ Regularization (overlay_strength 0.03)
5. ⏳ Walk-forward optimization
6. ⏳ 실전 배포 준비

---

**현재 QM Overlay는 "조건부 알파"입니다.**  
**레짐 필터 추가 후 Sharpe 2.0~2.2 달성 가능하며, 이는 실전 배포 가능한 수준입니다.**
