# Conclu.txt 문서 정독 분석 (2차)

## 📌 핵심 메시지

**최우선 과제**: Vol-Weighted Base는 임시방편이고, **실제 ARES7 base weights**가 필요하다.

하지만 문서는 다음과 같은 단계적 접근을 권장:

1. **단기 (지금)**: Vol-Weighted Base로 Overlay 구조 검증
2. **중기 (구조 검증 후)**: ARES7 실제 weights 추출

---

## 🎯 문서가 강조하는 3가지 핵심 포인트

### 1. EW Base의 치명적 문제

**문제점**:
- EW는 팩터 편향 때문에 PEAD와 예상치 못한 상호작용
- 거래비용이 실제 ARES7보다 과장됨
- 현재 overlay 음의 알파의 절반은 EW base 때문

**결론**:
> "EW base에서는 Overlay를 평가하면 안 된다"
> "ARES7 base weight에서만 진짜 판단 가능"

### 2. 실행 우선순위 (문서 제시)

| 우선순위 | 해야 할 일 | 이유 |
|---------|-----------|------|
| 1 | ARES7 Base Weights CSV 생성 | Overlay 평가의 토대. EW에서는 절대 최종판단 못함 |
| 2 | Budget=3%, Horizon=15d 단발 테스트 | 구조 전환 전에 "튜닝으로 살릴 수 있나?" 빠르게 체크 |
| 3 | **Pure Tilt Overlay v2** 실험 | 거래비용 문제를 해결할 수 있는 핵심 구조 개선 |
| 4 | Grid Search (36개 조합) | 구조가 살아있다면 최적 파라미터 찾기 |
| 5 | 시그널 개선 (SUE, Buyback) | 마지막 단계. 엔진 안정화 후에만 시도 |

### 3. Pure Tilt 구조의 중요성

**현재 Budget Carve-out 모델의 문제**:
- 매일 rebalance + double-trading 구조
- 구조적으로 비용을 못 이김
- Turnover 1246% → 비용 2.5%

**Pure Tilt 방식**:
- Overlay를 위해 신규 매수/매도하지 않음
- ARES7 weight 안에서 비중만 살짝 "기울임"
- 이벤트 오픈/만기 때만 미세조정
- Turnover가 구조적으로 수십~수백% 수준으로 감소

**결론**:
> "Pure Tilt 실험 없이 Overlay 판단하면 안 된다"

---

## 🔄 문서의 단계적 접근 (Market-Cap vs ARES7)

### 문서가 제시한 현실적 로드맵

#### Phase 1: Vol-Weighted Base (현재)
- ✅ **이미 완료됨**
- EW보다 현실적
- Overlay 구조 테스트에 충분
- 빠른 구현

**장점**:
- Small-cap/High-vol overweight 편향 제거
- 대형주/안정주 비중 증가
- EW보다 turnover/비용이 현실에 가까움
- ARES7 weights로 갈아타기 쉬움

**단점**:
- 여전히 "진짜 ARES7"은 아님
- 최종 프로덕션 성능은 ARES7 weights로 재검증 필요

#### Phase 2: ARES7 Weights 추출 (나중에)

**조건**: Vol-Weighted Base에서 다음이 확인되면
- Net Incremental Sharpe > 0.1~0.2
- 비용 감안해도 음수 아님
- MDD 크게 안 깨짐

**그때 투자할 가치 발생**:
- 서브 전략(E1_LS, C1_MR, Factor 등) 엔진 파기
- 종목 레벨 weight logging 추가
- 전략 weight × 종목 weight 합성

---

## 🚨 문서가 지적하는 현재 상황의 문제

### 문제 1: ARES7 앙상블은 "전략 레벨" weight만 제공

```python
calculate_risk_parity_weights()  # 전략 간 비중
calculate_sharpe_weighted()      # 전략 간 비중
```

이 함수들이 리턴하는 건:
- `{'E1_LS': 0.3, 'C1_MR': 0.2, 'Factor': 0.5}` (전략 레벨)

우리가 필요한 건:
- `{'AAPL': 0.012, 'MSFT': 0.008, ...}` (종목 레벨)

### 문제 2: 종목 레벨 weight는 각 서브 전략 내부에 숨어있음

**해결 방법**:
1. 각 서브 전략 엔진 찾기
2. 각 엔진에 weight logging 추가
3. 상위 앙상블에서 합성: `전략 weight × 종목 weight`

**난이도**: 높음 (여러 엔진 수정 + 테스트)

---

## 💡 문서가 제시한 ARES7 Weight 추출 방법

### 방법 1: 백테스트 루프에서 직접 추출

```python
def run_backtest(..., save_weights=False):
    weights_history = {}
    
    for date in trading_days:
        w_t = engine.get_weights(date)
        weights_history[date] = w_t
        # PnL 계산...
    
    if save_weights:
        save_weights_to_csv(weights_history, OUTPUT_CSV)
```

### 방법 2: Weight 히스토리 로깅

```python
class ARES7Engine:
    def __init__(self):
        self.weight_history = []
    
    def log_weights(self, current_date, weights_dict):
        for symbol, w in weights_dict.items():
            self.weight_history.append({
                "date": current_date,
                "symbol": symbol,
                "weight": float(w),
            })
    
    def save_weight_history(self, output_path):
        df = pd.DataFrame(self.weight_history)
        # normalize, sort, save...
```

### 필요한 CSV 포맷

```csv
date,symbol,weight
2018-01-02,AAPL,0.0123
2018-01-02,MSFT,0.0087
...
```

---

## 🎯 문서가 제시한 즉시 실행 항목

### 우선순위 2: Budget=3%, Horizon=15d 테스트

**현재 문제**:
- Budget=10%, Horizon=5d → 거래비용 폭사
- Turnover 1246% → 비용 2.5%

**개선안**:
- Budget: 10% → 2~3%
- Horizon: 5d → 10~15d
- Rank threshold: 0.9 → 0.95

**실행 명령**:
```bash
python -m research.pead.run_ares8_overlay --budget 0.03 --horizon 15
```

**기대 결과**:
- Incremental Sharpe가 0 근처만 나와도 성공
- 구조적 전환의 필요성 판단용

### 우선순위 3: Pure Tilt 구조 전환

**핵심 아이디어**:
- 신규 매수/매도 없이 ARES7 weight 내에서 재배분
- 거래비용 급감
- Turnover = ARES7 수준 + 작은 overlay 변동

**구현 필요**:
- `apply_overlay_budget()` 함수를 Pure Tilt 방식으로 재작성
- 현재: Carve-out (신규 포지션 생성)
- 개선: Tilt (기존 포지션 재배분)

---

## 📊 문서의 ROI 분석

### Vol-Weighted Base 선택 이유

| 옵션 | ROI | 구현 시간 | 정확도 |
|------|-----|----------|--------|
| SF1 Marketcap 재다운로드 | 낮음 | 길음 | 높음 |
| Price × Shares | 낮음 | 중간 | 중간 |
| **Vol-Weighted** | **높음** | **짧음** | **충분** |
| EW 그대로 | 낮음 | 0 | 낮음 |

**결론**:
> "지금 Jason이 정말 알고 싶은 건 'Overlay 구조가 살아있는가?'이지 '베이스가 시총이냐 EW냐?'가 아니다"

---

## 🔥 문서가 강조하는 핵심 통찰

### 1. 베이스 선택의 우선순위

**현재 단계**: Overlay 구조 검증
- Vol-Weighted Base로 충분
- 구조적 문제(Pure Tilt vs Budget) 해결이 우선

**다음 단계**: 프로덕션 준비
- ARES7 실제 weights 필요
- 최종 성능/리스크 검증

### 2. 작업 순서의 중요성

**잘못된 순서**:
1. ARES7 weights 추출 (heavy)
2. Overlay 구조 실험
3. 구조가 안 맞으면 처음부터 다시

**올바른 순서**:
1. Vol-Weighted Base로 Overlay 구조 검증
2. 구조가 살만하면 ARES7 weights 추출
3. 최종 검증

**이유**:
- 엔진 수정 vs Overlay 수정이 섞이면 디버깅 어려움
- ROI 최적화

### 3. Pure Tilt의 중요성

**문서가 반복 강조**:
> "Pure Tilt 실험 없이 Overlay 판단하면 안 된다"
> "Budget-model overlay는 구조적으로 과도한 Turnover를 만든다"
> "해결책은 ARES7 내부 weight를 재배분하는 Pure Tilt 방식이다"

**현재 상황**:
- Budget Carve-out 모델 사용 중
- 구조적으로 비용을 못 이김
- Pure Tilt 전환이 핵심 개선 포인트

---

## ✅ 현재 완료 상태 vs 문서 권장사항

| 문서 권장 | 현재 상태 | 비고 |
|----------|----------|------|
| Vol-Weighted Base | ✅ 완료 | 243,151 레코드 |
| Budget=3%, Horizon=15d 테스트 | 🔄 Grid Search 실행 중 | 24개 조합 포함 |
| Pure Tilt 구조 전환 | ❌ 미착수 | **최우선 과제** |
| ARES7 Weights 추출 | ❌ 보류 | Pure Tilt 검증 후 |
| Buyback 신호 | 🔄 추출 중 | 10개 티커 테스트 |

---

## 🎯 문서 기반 수정된 실행 계획

### Phase 3 (현재): PEAD 최적화
- ✅ Vol-Weighted Base 완료
- 🔄 Grid Search 실행 중
- ⏭️ **Pure Tilt 구조 구현** (최우선)

### Phase 4: Pure Tilt 검증
- Pure Tilt 방식으로 overlay 재구현
- Vol-Weighted Base에서 성능 검증
- Turnover/비용 대폭 감소 확인

### Phase 5: ARES7 Integration (조건부)
- **조건**: Pure Tilt에서 Net Incremental Sharpe > 0.1
- 서브 전략 엔진 파기
- 종목 레벨 weight logging 추가
- ARES7 실제 weights로 최종 검증

### Phase 6: Buyback & Multi-Signal
- Buyback 알파 분석
- PEAD + Buyback 앙상블
- 최종 성능 평가

---

## 🚀 즉시 실행 가능한 액션 아이템

### 1. Grid Search 완료 대기 (진행 중)
- 현재 실행 중
- 완료 후 결과 분석

### 2. Pure Tilt 구조 구현 (최우선)
- `overlay_engine.py`에 Pure Tilt 방식 추가
- 기존 Budget Carve-out과 비교
- Turnover/비용 대폭 감소 기대

### 3. Budget=3%, Horizon=15d 단발 테스트
- Grid Search 결과에 이미 포함됨
- 별도 실행 불필요

### 4. ARES7 Weights 추출 (보류)
- Pure Tilt 검증 후 결정
- 구조가 살만하면 투자

---

## 📝 문서의 핵심 교훈

1. **베이스 선택보다 구조 개선이 우선**
   - Vol-Weighted → ARES7는 나중에
   - Budget → Pure Tilt가 먼저

2. **ROI 중심 의사결정**
   - Heavy한 작업은 가치 검증 후
   - 단계적 접근으로 리스크 최소화

3. **Pure Tilt가 게임 체인저**
   - 거래비용 문제의 구조적 해결책
   - 이것 없이 Overlay 판단 불가

4. **ARES7 Weights는 최종 단계**
   - Overlay 구조 검증 후
   - 프로덕션 준비 단계에서

---

## 🎯 최종 결론

**문서의 핵심 메시지**:
1. ✅ Vol-Weighted Base는 잘했음 (현재 단계에 적합)
2. 🔥 **Pure Tilt 구조 전환이 최우선 과제**
3. ⏭️ ARES7 Weights는 Pure Tilt 검증 후

**다음 단계**:
1. Grid Search 완료 대기
2. **Pure Tilt Overlay v2 구현** (최우선)
3. Vol-Weighted Base에서 Pure Tilt 검증
4. 성공 시 ARES7 Weights 추출 고려

**현재 진행 방향**: ✅ 올바름
- Vol-Weighted Base 생성 완료
- Grid Search로 파라미터 최적화 중
- 다음은 Pure Tilt 구조 전환

**문서가 추가로 강조하는 것**:
- Pure Tilt 없이는 최종 판단 불가
- ARES7 Weights는 그 다음 단계
