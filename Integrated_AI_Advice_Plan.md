# ARES-7 통합 실행 계획 (3개 AI 조언 기반)

**날짜**: 2025년 11월 25일  
**목표**: Sharpe 1.255 → 1.8+ (6개월 로드맵)

---

## AI 조언 핵심 요약

### Grok (xAI)
- 단기 momentum 실패는 **정상**
- 추천: Mean Reversion, Trend Following, Pairs Trading
- Walk-Forward Optimization

### Gemini (Google)
- Look-ahead bias는 시장 마이크로구조 문제
- 추천: 장기 Momentum (20-60일), Fama-French Factors
- Regime Switching, Portfolio Optimization

### Claude (Anthropic) - **가장 구체적**
- **Signal Decay**: 3일 momentum의 알파는 몇 시간 내 소멸
- **Crowding**: 단기 시그널은 가장 혼잡
- 구체적 코드 예시 제공

---

## 통합 실행 계획

### Phase 1: Execution Alpha (1-2개월)
**목표**: Sharpe 1.255 → 1.4-1.5

#### 1.1 Transaction Cost Modeling
```python
# 현실적 비용 (bps)
spread_cost = 5  # Half-spread
market_impact = 10 * sqrt(position_size / adv)
total_cost = spread_cost + market_impact

# 거래 조건
if expected_return > 2 * total_cost:
    execute_trade()
```

#### 1.2 Volatility Targeting
```python
# 목표 변동성: 10% 연간
target_vol = 0.10
current_vol = rolling_std(returns, 60) * sqrt(252)
leverage = target_vol / current_vol
```

#### 1.3 Dynamic Position Sizing
```python
# Drawdown 기반 조정
position_size = base_size * (1 - current_dd / max_acceptable_dd)
```

**예상 개선**: +0.15~0.25 Sharpe

---

### Phase 2: New Alpha Sources (3-4개월)
**목표**: Sharpe 1.4-1.5 → 1.6-1.7

#### 2.1 Robust Momentum (Claude 제안)
```python
# 3일 + 10일 + 21일 조합
robust_momentum = (
    0.5 * (close[-1] - close[-4]) / close[-4] +
    0.3 * (close[-1] - close[-11]) / close[-11] +
    0.2 * (close[-1] - close[-22]) / close[-22]
) / rolling_std(returns, 20)
```

**특징**:
- 올바른 타이밍 (전일 데이터)
- 변동성 조정
- 다중 기간 조합

**목표**: Sharpe 0.6+

#### 2.2 Overnight Gap Strategy
```python
# Close-to-Open momentum fade
signal = (close_today - close_yesterday) / close_yesterday
position = -signal  # Fade the move
entry = next_day_open
exit = next_day_close
```

**목표**: Sharpe 0.5+

#### 2.3 Sector Rotation (Gemini 제안)
```python
# 20일 vs 60일 MA 크로스오버
signal = MA(sector_price, 20) - MA(sector_price, 60)
position = sign(signal)
```

**목표**: Sharpe 0.7+

**예상 개선**: +0.2~0.3 Sharpe

---

### Phase 3: Portfolio Optimization (5-6개월)
**목표**: Sharpe 1.6-1.7 → 1.8+

#### 3.1 Adaptive Weighting (Claude 제안)
```python
# Softmax 기반 동적 비중
weights = softmax(rolling_sharpe_ratios / temperature)
ensemble_signal = sum(weights * signals)
```

#### 3.2 Regime Switching (Gemini 제안)
```python
# VIX 기반 레짐 분류
if VIX > 25:
    regime = "high_vol"
    weights = [0.6, 0.2, 0.2]  # Low-Vol 중심
elif VIX < 15:
    regime = "low_vol"
    weights = [0.3, 0.4, 0.3]  # Momentum 중심
else:
    regime = "normal"
    weights = [0.4, 0.3, 0.3]
```

#### 3.3 Correlation-Based Risk Management
```python
# 전략 간 상관 > 0.8 시 포지션 축소
if rolling_corr(strategy_A, strategy_B) > 0.8:
    reduce_positions(0.5)
```

**예상 개선**: +0.1~0.2 Sharpe

---

## 구체적 구현 순서

### Week 1-2: Transaction Cost & Vol Targeting
1. ✅ 거래 비용 모델링 추가
2. ✅ Volatility Targeting 구현
3. ✅ 4-Way Ensemble에 적용
4. ✅ 백테스트 재실행

**예상**: Sharpe 1.255 → 1.35

### Week 3-4: Robust Momentum
1. ✅ Claude의 Robust Momentum 구현
2. ✅ 올바른 타이밍 검증
3. ✅ 파라미터 최적화
4. ✅ 5-Way Ensemble 테스트

**예상**: Sharpe 1.35 → 1.45

### Week 5-6: Overnight Gap Strategy
1. ✅ Overnight Gap 전략 구현
2. ✅ 백테스트
3. ✅ 6-Way Ensemble 테스트

**예상**: Sharpe 1.45 → 1.55

### Week 7-8: Sector Rotation
1. ✅ Sector Rotation 구현
2. ✅ 7-Way Ensemble 테스트

**예상**: Sharpe 1.55 → 1.65

### Week 9-10: Adaptive Weighting
1. ✅ Softmax 기반 동적 비중
2. ✅ Regime Switching
3. ✅ 최종 Ensemble

**예상**: Sharpe 1.65 → 1.8+

---

## 핵심 원칙 (3개 AI 공통)

1. ✅ **올바른 타이밍**: 전일 데이터만 사용
2. ✅ **장기 시그널**: 20-60일 (단기 포기)
3. ✅ **거래 비용**: 현실적 모델링
4. ✅ **동적 조정**: Volatility Targeting, Regime Switching
5. ✅ **분산 효과**: 낮은 상관 전략 추가

---

## 예상 결과

### 보수적 시나리오

| Phase | Sharpe | 개선 |
|:---|---:|---:|
| 현재 | 1.255 | - |
| Phase 1 (Execution) | 1.35 | +0.10 |
| Phase 2 (New Alpha) | 1.55 | +0.20 |
| Phase 3 (Optimization) | 1.70 | +0.15 |

### 낙관적 시나리오

| Phase | Sharpe | 개선 |
|:---|---:|---:|
| 현재 | 1.255 | - |
| Phase 1 (Execution) | 1.45 | +0.20 |
| Phase 2 (New Alpha) | 1.70 | +0.25 |
| Phase 3 (Optimization) | 1.90 | +0.20 |

---

## 다음 단계

**즉시 시작**:
1. ✅ Transaction Cost Modeling
2. ✅ Volatility Targeting
3. ✅ Robust Momentum 구현

**목표 달성 가능성**: 80% (Claude의 로드맵 기반)

**시작합니다!**
