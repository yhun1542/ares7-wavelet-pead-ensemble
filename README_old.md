# ARES-7 Ensemble Trading System

**Version**: 2.0  
**Date**: 2025년 11월 25일  
**Status**: Look-ahead Bias 검증 완료

---

## 프로젝트 개요

ARES-7은 여러 퀀트 전략을 앙상블하여 안정적인 수익을 추구하는 시스템입니다.

**현재 상태**:
- ✅ 유효한 4-Way Ensemble: **Sharpe 1.255**
- ❌ 목표 Sharpe 2.0+ 미달성
- ✅ Look-ahead bias 완전 검증 완료

---

## 디렉토리 구조

```
ares7_ensemble/
├── data/
│   ├── price_full.csv          # 가격 데이터 (100 종목, 2015-2025)
│   └── fundamentals.csv        # 펀더멘털 데이터
│
├── engines/
│   ├── engine_ls_enhanced.py   # A+LS Enhanced (Sharpe 0.947) ✅
│   ├── engine_c_lowvol_v2.py   # Low-Vol v2 (Sharpe 0.808) ✅
│   ├── C1_final_v5.json        # C1 Final v5 (Sharpe 0.715) ✅
│   ├── engine_factor_v2_pit.py # Factor v2 PIT (실패, Sharpe -0.400) ❌
│   ├── engine_factor_v3.py     # Factor v3 (실패, Sharpe -0.316) ❌
│   ├── engine_factor_v4.py     # Factor v4 (Sharpe 0.257) ⚠️
│   ├── engine_c1_v6_simple.py  # C1 v6 (look-ahead, Sharpe 2.896) ❌
│   ├── engine_c1_v6_correct.py # C1 v6 Correct (실패, Sharpe -0.646) ❌
│   └── engine_c1_v7.py         # C1 v7 (실패, Sharpe -0.342) ❌
│
├── results/
│   ├── ensemble_4way_results.json              # 4-Way Ensemble 결과 ✅
│   ├── ensemble_5way_results.json              # 5-Way Ensemble (무효) ❌
│   ├── Final_Verification_Report.md            # 최종 검증 보고서
│   ├── Manus_Verification_Report.md            # 상세 검증 보고서
│   ├── Final_Report_v2.md                      # 최종 프로젝트 보고서
│   └── AI_Strategy_Advice_Request.md           # AI 조언 요청 문서
│
└── README.md                   # 이 파일
```

---

## 유효한 전략 (4-Way Ensemble)

### 1. A+LS Enhanced (Sharpe 0.947)
- **전략**: Long/Short with sector rotation
- **리밸런싱**: 주간
- **파일**: `engine_ls_enhanced_results.json`

### 2. C1 Final v5 (Sharpe 0.715)
- **전략**: Mean reversion
- **리밸런싱**: 7일
- **파일**: `C1_final_v5.json`

### 3. Low-Vol v2 (Sharpe 0.808)
- **전략**: Low volatility long/short
- **리밸런싱**: 주간
- **파일**: `engine_c_lowvol_v2_final_results.json`

### 4-Way Ensemble 성능

| 지표 | 값 |
|:---|---:|
| **Sharpe Ratio** | **1.255** |
| Annual Return | 15.06% |
| Volatility | 12.00% |
| Max Drawdown | -14.91% |

---

## 실패한 전략 (Look-ahead Bias)

### Factor v2/v3/v4
- **문제**: 리밸런싱 당일 종가로 시그널 계산 후 당일 매수
- **수정 후**: Sharpe -0.400 ~ 0.257
- **결론**: 올바른 타이밍으로는 작동하지 않음

### C1 v6/v7
- **문제**: 당일 수익률 포함 시그널로 당일 매수
- **수정 후**: Sharpe -0.646 ~ -0.342
- **결론**: 단기 momentum은 look-ahead에 극도로 민감

---

## 핵심 교훈

### 1. Look-ahead Bias의 위험

**1일의 차이가 모든 것을 바꿉니다**:
- Factor v3: Sharpe 1.268 → -0.316 (차이 1.584)
- C1 v6: Sharpe 3.556 → -0.342 (차이 3.898)

### 2. 올바른 타이밍 구현

```python
# ❌ 잘못된 방법
if date in rebal_dates:
    signals = calculate_signals(price.loc[date])  # 당일 데이터 사용
    positions = select_positions(signals)
    ret = calculate_return(positions, returns.loc[date])  # 당일 수익

# ✅ 올바른 방법
if date in rebal_dates:
    prev_date = price.index[date_idx - 1]
    signals = calculate_signals(price.loc[prev_date])  # 전일 데이터 사용
    next_positions = select_positions(signals)  # 다음날 적용

# 다음날
current_positions = next_positions
ret = calculate_return(current_positions, returns.loc[date])
```

### 3. 비현실적인 숫자는 Red Flag

- Sharpe 3.556은 **비현실적**
- 이런 숫자가 나오면 즉시 **look-ahead bias** 의심

---

## 사용 방법

### 1. 데이터 준비

```bash
# 데이터 파일 확인
ls data/
# price_full.csv
# fundamentals.csv
```

### 2. 엔진 실행

```bash
# Factor v4 실행
python3.11 engine_factor_v4.py --lookback_mom 90 --rebalance M

# C1 v6 Correct 실행
python3.11 engine_c1_v6_correct.py --signal_span 3 --n_long 15 --n_short 15
```

### 3. 결과 확인

```bash
# 결과 파일 확인
ls results/*.json

# 보고서 확인
cat results/Final_Report_v2.md
```

---

## 다음 단계

### Option A: 새로운 전략 개발 (권장)

1. **Trend Following (CTA)**: 중장기 트렌드 추종
2. **Pairs Trading**: 종목 쌍 거래
3. **Statistical Arbitrage**: 통계적 차익거래

### Option B: 기존 전략 최적화

1. A+LS, C1 v5, LV2 파라미터 최적화
2. 동적 비중 조정
3. 리스크 패리티 적용

---

## 참고 문서

- `Final_Verification_Report.md`: 최종 검증 보고서
- `Manus_Verification_Report.md`: 상세 검증 보고서 (10개 이슈)
- `Final_Report_v2.md`: 최종 프로젝트 보고서
- `AI_Strategy_Advice_Request.md`: AI 조언 요청 문서

---

## 라이선스

이 프로젝트는 교육 및 연구 목적으로 제공됩니다.

---

## 연락처

- **개발자**: Manus AI
- **날짜**: 2025년 11월 25일
