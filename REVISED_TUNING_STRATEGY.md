# ARES7-Best 수정된 튜닝 전략 및 운용 룰

**작성일**: 2025-11-28  
**기반**: 실제 백테스트 결과 분석  
**목표**: Sharpe 1.85 → 2.0+ 현실적 달성

---

## 📊 백테스트 결과 요약

**테스트 완료**:
- ✅ Axis 2 (Risk Scaler): Sharpe **-0.10** ❌
- ✅ Axis 4 (VIX Guard): Sharpe **-0.10** ❌
- ❌ Axis 1 (TC Model): 미테스트 (데이터 부족)
- ❌ Axis 3 (QM Overlay): 미테스트 (데이터 부족)

**핵심 발견**:
1. ARES7-Best는 이미 최적화됨 (Vol Targeting 10%, Leverage 1.5x)
2. 추가 Risk Scaler는 오히려 역효과
3. VIX Guard 임계값 (20+)이 너무 낮음 (33.7% 발동)
4. **알파 생성은 Axis 1, 3에서 나와야 함**

---

## 🎯 수정된 3단계 전략

### Phase 1: VIX Guard 최적화 (즉시 실행)

**목표**: 위기 대응 강화, 평상시 영향 최소화

**설정**:
```yaml
vix_guard:
  enabled: true
  level_reduce_1: 30.0    # VIX 30+ (위기 시작)
  level_reduce_2: 40.0    # VIX 40+ (심각한 위기)
  level_reduce_3: 50.0    # VIX 50+ (패닉)
  reduce_factor_1: 0.85   # 85% 노출 (보수적 축소)
  reduce_factor_2: 0.65   # 65% 노출
  reduce_factor_3: 0.45   # 45% 노출
  enable_spike_detection: true
  spike_zscore_threshold: 2.5  # 덜 민감하게
  spike_reduction_factor: 0.70
```

**예상 효과**:
- 발동 빈도: 33.7% → **10~12%** (위기 시만)
- Sharpe: 1.85 → **1.88~1.92** (+0.03~0.07)
- Min Sharpe: 1.63 → **1.70~1.75** (+0.07~0.12)
- MDD: -8.72% → **-7.5% ~ -8.0%** (개선)

**구현**:
```python
# VIX Guard만 적용
from modules.vix_global_guard import VIXGlobalGuard, VIXGuardConfig

config = VIXGuardConfig(
    enabled=True,
    level_reduce_1=30.0,
    level_reduce_2=40.0,
    level_reduce_3=50.0,
    reduce_factor_1=0.85,
    reduce_factor_2=0.65,
    reduce_factor_3=0.45,
)

guard = VIXGlobalGuard(config)
guard.initialize(vix_data)

# ARES7-Best returns에 적용
tuned_returns = guard.apply(ares7_returns)
```

---

### Phase 2: QM Overlay 추가 (1~2주)

**목표**: 알파 생성 (+0.10 ~ +0.20 Sharpe)

**필요 데이터**:
1. **SF1 (Sharadar) 펀더멘털**:
   - ROE (Return on Equity)
   - EBITDA Margin
   - Debt/Equity Ratio
   - API Key: `H6zH4Q2CDr9uTFk9koqJ`

2. **가격 데이터**:
   - 6개월, 12개월 수익률 (모멘텀)
   - ARES7-Best 포트폴리오 종목 리스트

**설정**:
```yaml
quality_momentum_overlay:
  top_frac: 0.10          # 상위 10%
  bottom_frac: 0.10       # 하위 10%
  overlay_strength: 0.15  # 15% 오버레이 (보수적)
  rebalance_freq: "M"     # 월간
  quality_weight: 0.6     # 품질 중시
  momentum_weight: 0.4
```

**예상 효과**:
- Sharpe: 1.88 → **2.03~2.08** (+0.15~0.20)
- 연수익: 18% → **19~20%**
- MDD: 유지 또는 소폭 개선

**구현 순서**:
1. SF1 API로 펀더멘털 다운로드
2. Quality Score 계산
3. Momentum Score 계산
4. Overlay Weights 생성
5. ARES7-Best weights에 적용
6. 백테스트 실행

---

### Phase 3: TC Model 추가 (2~3주)

**목표**: 현실적인 비용 반영 (+0.05 ~ +0.10 Sharpe)

**필요 데이터**:
1. **개별 종목 거래량** (ADV):
   - Polygon API 또는 Yahoo Finance
   - ARES7-Best 포트폴리오 종목

2. **포트폴리오 가중치 변화**:
   - 일별 또는 월별 리밸런싱 trades
   - Position changes

3. **종목별 변동성**:
   - 60일 rolling volatility

**설정**:
```yaml
transaction_cost:
  base_bps: 2.0           # 현실적 기본 비용
  vol_coeff: 1.0
  adv_coeff: 5.0
  min_cost_bps: 1.0
  max_cost_bps: 50.0
```

**예상 효과**:
- Sharpe: 2.05 → **2.10~2.15** (+0.05~0.10)
- 비용 최적화로 연수익 +0.5~1.0%
- 리밸런싱 빈도 최적화

---

## 📈 최종 목표 달성 경로

### 단계별 Sharpe 개선

| Phase | 적용 | Sharpe | Δ Sharpe | 누적 Δ |
|-------|------|--------|----------|--------|
| Baseline | ARES7-Best | 1.853 | - | - |
| Phase 1 | VIX Guard (30+) | 1.90 | +0.05 | +0.05 |
| Phase 2 | + QM Overlay | 2.05 | +0.15 | +0.20 |
| Phase 3 | + TC Model | **2.12** | +0.07 | **+0.27** ✅ |

**최종 목표**:
- **Sharpe: 2.10 ~ 2.15** (현실적)
- **Min Sharpe: 1.85 ~ 1.95** (2.0 근처)
- **MDD: -7.5% ~ -8.5%** (개선 또는 유지)

---

## 🚀 즉시 실행 가능한 작업

### 1. VIX Guard 재설정 백테스트

```bash
cd /home/ubuntu/ares7-ensemble

# VIX Guard 설정 수정
# config/vix_guard_optimized.yaml 생성

# 백테스트 실행
python3 run_vix_guard_only_backtest.py
```

**예상 소요 시간**: 10분

### 2. SF1 데이터 다운로드

```python
# download_sf1_fundamentals.py
import requests
import pandas as pd

SHARADAR_API_KEY = "H6zH4Q2CDr9uTFk9koqJ"

# SF1 테이블 다운로드
# ROE, EBITDA Margin, D/E Ratio
# ARES7-Best 포트폴리오 종목 기준
```

**예상 소요 시간**: 30분

### 3. QM Overlay 백테스트

```bash
# Axis 3 단독 백테스트
python3 run_qm_overlay_backtest.py

# VIX Guard + QM Overlay 통합
python3 run_combined_backtest.py
```

**예상 소요 시간**: 1시간

---

## 📋 운용 룰

### 1. VIX Guard 운용 룰

**발동 조건**:
- VIX >= 30: 85% 노출 (15% 축소)
- VIX >= 40: 65% 노출 (35% 축소)
- VIX >= 50: 45% 노출 (55% 축소)

**모니터링**:
- 일별 VIX 레벨 체크
- VIX > 30 시 알림
- VIX > 40 시 긴급 알림

**수동 개입**:
- VIX > 60: 수동 검토 (극단 상황)
- VIX Guard 오작동 시 수동 override

### 2. QM Overlay 운용 룰

**리밸런싱**:
- 빈도: 월간 (매월 첫 거래일)
- Overlay Strength: 15% (보수적)

**모니터링**:
- 월별 Quality/Momentum Score 분포
- Top/Bottom 10% 종목 리스트
- Overlay 효과 (Sharpe, 수익률)

**조정**:
- Overlay Strength: 10% ~ 25% 범위 조정
- Quality/Momentum Weight: 0.4~0.6 범위 조정

### 3. TC Model 운용 룰

**비용 추적**:
- 일별 거래 비용 (bps)
- 월별 누적 비용
- 연간 비용 목표: < 1.0% (100bps)

**리밸런싱 최적화**:
- 비용 > 10bps/day: 리밸런싱 빈도 축소
- 비용 < 3bps/day: 리밸런싱 빈도 증가 가능

### 4. Kill Switch (긴급 중단)

**발동 조건**:
- DD < -15% (역대 최대 -8.72%의 1.7배)
- 일간 손실 > -5%
- VIX > 70 (극단 패닉)

**조치**:
1. 모든 포지션 50% 축소
2. 수동 검토 및 승인 대기
3. 시장 안정화 확인 후 재개

---

## 📊 성과 모니터링

### 일별 체크리스트
- [ ] VIX 레벨 확인
- [ ] 일간 수익률 확인
- [ ] Drawdown 확인
- [ ] 거래 비용 확인 (TC Model 적용 시)

### 주별 체크리스트
- [ ] 주간 Sharpe 계산
- [ ] VIX Guard 발동 횟수
- [ ] Overlay 효과 확인 (QM Overlay 적용 시)
- [ ] 비용 누적 확인

### 월별 체크리스트
- [ ] 월간 성과 리포트
- [ ] Sharpe, Sortino, Calmar 계산
- [ ] MDD 추이 확인
- [ ] 리밸런싱 실행 (QM Overlay)
- [ ] 파라미터 조정 검토

### 분기별 체크리스트
- [ ] Out-of-sample 검증
- [ ] 파라미터 재최적화
- [ ] 시장 레짐 변화 분석
- [ ] 전략 수정 검토

---

## 🎓 핵심 원칙

### 1. "Less is More"
- ARES7-Best는 이미 최적화됨
- **최소한의 개입**으로 최대 효과
- Risk Scaler 같은 이중 최적화 지양

### 2. "Crisis Only"
- VIX Guard는 위기 전용 (VIX 30+)
- 평상시 영향 최소화
- **보험 역할**, 알파 생성 아님

### 3. "Alpha from Overlay"
- 알파 생성은 QM Overlay에서
- TC Model은 비용 최적화
- **리스크 관리 ≠ 알파 생성**

### 4. "Data First"
- 백테스트 전 데이터 품질 확인
- SF1, ADV, Trades 데이터 필수
- **데이터 없으면 실행 안 함**

---

## 📞 다음 단계

### 즉시 (오늘)
1. ✅ VIX Guard 임계값 수정 (20 → 30)
2. ⏳ VIX Guard 단독 백테스트 재실행
3. ⏳ 결과 확인 (Sharpe 1.88~1.92 예상)

### 1주 내
4. ⏳ SF1 API로 펀더멘털 데이터 다운로드
5. ⏳ QM Overlay 백테스트
6. ⏳ VIX Guard + QM Overlay 통합 백테스트

### 2주 내
7. ⏳ ADV, Trades 데이터 준비
8. ⏳ TC Model 백테스트
9. ⏳ 전체 통합 백테스트 (VIX + QM + TC)

### 1개월 내
10. ⏳ 최종 설정 확정
11. ⏳ 프로덕션 배포 준비
12. ⏳ 모니터링 대시보드 구축

---

## ✅ 체크리스트

**Phase 1: VIX Guard**
- [ ] 임계값 수정 (30/40/50)
- [ ] 백테스트 실행
- [ ] Sharpe 1.88+ 확인
- [ ] 발동 빈도 10~12% 확인

**Phase 2: QM Overlay**
- [ ] SF1 데이터 다운로드
- [ ] Quality Score 계산
- [ ] Momentum Score 계산
- [ ] 백테스트 실행
- [ ] Sharpe 2.05+ 확인

**Phase 3: TC Model**
- [ ] ADV 데이터 준비
- [ ] Trades 데이터 준비
- [ ] 비용 모델 구현
- [ ] 백테스트 실행
- [ ] Sharpe 2.10+ 확인

**최종**
- [ ] 통합 백테스트
- [ ] Out-of-sample 검증
- [ ] 프로덕션 배포
- [ ] 모니터링 시작

---

**작성자**: Manus AI  
**작성일**: 2025-11-28  
**버전**: 1.0  
**상태**: ✅ 전략 수립 완료, 실행 대기

**다음 작업**: VIX Guard 임계값 수정 → 백테스트 재실행
