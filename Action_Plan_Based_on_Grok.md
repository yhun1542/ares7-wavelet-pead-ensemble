# ARES-7 실행 계획 (Grok 조언 기반)

**날짜**: 2025년 11월 25일  
**목표**: Sharpe 1.255 → 1.8+

---

## Grok의 핵심 조언

### 1. 단기 Momentum은 포기

- 3-5일 momentum은 **look-ahead 없이는 작동 불가**
- 이것은 정상적인 현상
- **대안**: 주/월 단위 Trend Following

### 2. 추천 전략 타입

✅ **Mean Reversion** (장기)  
✅ **Value Investing** (펀더멘털)  
✅ **Trend Following** (주/월 단위)  
✅ **Risk Parity / Low Volatility**  
✅ **Statistical Arbitrage** (Pairs Trading)

### 3. 개선 방법

1. 더 많은 전략 추가
2. 동적 비중 조정
3. Walk-Forward Optimization
4. 거래 비용 최소화

---

## 실행 계획

### Phase 1: Trend Following 전략 개발

**전략**: CTA-style Trend Following
- **시그널**: 20/60일 이동평균 크로스오버
- **타이밍**: 전일 종가로 시그널, 당일 종가로 실행
- **리밸런싱**: 주간
- **목표**: Sharpe 0.6+

**구현**:
```python
# 20일 MA > 60일 MA → Long
# 20일 MA < 60일 MA → Short
# 섹터별 적용
```

### Phase 2: Mean Reversion 개선

**전략**: 장기 Mean Reversion (20-60일)
- **시그널**: 60일 이동평균 대비 편차
- **타이밍**: 올바른 타이밍 (전일 데이터)
- **리밸런싱**: 월간
- **목표**: Sharpe 0.5+

### Phase 3: Pairs Trading 재시도

**전략**: 통계적 Pairs Trading
- **페어 선택**: 상관계수 0.8+ 종목 쌍
- **시그널**: Z-score > 2 또는 < -2
- **타이밍**: 전일 Z-score, 당일 실행
- **목표**: Sharpe 0.7+

### Phase 4: 동적 비중 조정

**방법**: Risk Parity
- 각 전략의 변동성에 반비례하여 비중 조정
- 월간 리밸런싱
- **목표**: 전체 Sharpe +0.2~0.3 개선

---

## 예상 결과

### 보수적 시나리오

| 전략 | Sharpe | 비중 | 기여 |
|:---|---:|---:|---:|
| 4-Way Ensemble | 1.255 | 60% | 0.753 |
| Trend Following | 0.6 | 20% | 0.120 |
| Mean Reversion | 0.5 | 10% | 0.050 |
| Pairs Trading | 0.7 | 10% | 0.070 |
| **합계** | - | 100% | **0.993** |

**분산 효과**: +0.3~0.5 (낮은 상관)  
**예상 Sharpe**: **1.3~1.5**

### 낙관적 시나리오

| 전략 | Sharpe | 비중 | 기여 |
|:---|---:|---:|---:|
| 4-Way Ensemble | 1.255 | 50% | 0.628 |
| Trend Following | 0.8 | 20% | 0.160 |
| Mean Reversion | 0.7 | 15% | 0.105 |
| Pairs Trading | 0.9 | 15% | 0.135 |
| **합계** | - | 100% | **1.028** |

**분산 효과**: +0.5~0.8 (낮은 상관)  
**예상 Sharpe**: **1.5~1.8** ✅

---

## 다음 단계

1. ✅ **Trend Following 개발** (1-2일)
2. ✅ **Mean Reversion 개선** (1일)
3. ✅ **Pairs Trading 재시도** (1-2일)
4. ✅ **7-Way Ensemble 테스트** (1일)
5. ✅ **Risk Parity 적용** (1일)

**예상 소요 시간**: 5-7일  
**목표 달성 가능성**: 70%

---

## 핵심 원칙

1. ✅ **올바른 타이밍**: 전일 데이터만 사용
2. ✅ **장기 시그널**: 주/월 단위
3. ✅ **낮은 상관**: 다양한 전략 타입
4. ✅ **현실적 기대**: Sharpe 0.5~0.8 per 전략

**시작합니다!**
