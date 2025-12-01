# ARES7 Tuning Quick Start Guide

**목표**: ARES7-Best Sharpe 1.85 → 2.15~2.45  
**소요 시간**: 10분 (설정) + 백테스트 시간  
**난이도**: ⭐⭐ (중급)

---

## 🚀 빠른 시작 (3단계)

### Step 1: 패키지 압축 해제

```bash
tar -xzf ares7_tuning_package.tar.gz
cd ares7-ensemble
```

### Step 2: 데이터 준비

ARES7-Best 기본 데이터를 준비합니다:

```python
# data_preparation.py (예시)
import pandas as pd

# 1. ARES7-Best 기본 수익률
ares7_returns = pd.read_csv('ares7_best_returns.csv', index_col=0, parse_dates=True)

# 2. 개별 종목 수익률
stock_returns = pd.read_csv('stock_returns.csv', index_col=0, parse_dates=True)

# 3. 포트폴리오 가중치
portfolio_weights = pd.read_csv('portfolio_weights.csv', index_col=0, parse_dates=True)

# 4. VIX 데이터
vix_data = pd.read_csv('vix_data.csv', index_col=0, parse_dates=True)

# 5. SF1 펀더멘털 데이터 (Axis 3용)
quality_data = {
    'roe': pd.read_csv('roe.csv', index_col=[0,1], parse_dates=True),
    'ebitda_margin': pd.read_csv('ebitda_margin.csv', index_col=[0,1], parse_dates=True),
    'debt_equity': pd.read_csv('debt_equity.csv', index_col=[0,1], parse_dates=True),
}
```

### Step 3: 백테스트 실행

```bash
# Conservative (안정적)
./run_tuning_backtest.sh conservative

# Moderate (균형)
./run_tuning_backtest.sh moderate

# Aggressive (공격적)
./run_tuning_backtest.sh aggressive

# 전체 실행
./run_tuning_backtest.sh all
```

---

## 📁 파일 구조

```
ares7-ensemble/
├── config/                                  # 설정 파일
│   ├── tuning_config_conservative.yaml     # 보수적 (Sharpe 2.15)
│   ├── tuning_config_moderate.yaml         # 중간 (Sharpe 2.30)
│   └── tuning_config_aggressive.yaml       # 공격적 (Sharpe 2.45)
│
├── risk/                                    # 리스크 관리 모듈
│   ├── transaction_cost_model_v2.py        # Axis 1: TC Model
│   └── global_risk_scaler.py               # Axis 2: Risk Scaler
│
├── modules/                                 # 전략 모듈
│   ├── overlay_quality_mom_v1.py           # Axis 3: QM Overlay
│   └── vix_global_guard.py                 # Axis 4: VIX Guard
│
├── tuning/
│   ├── backtest/
│   │   └── ares7_tuning_backtest_v1.py     # 통합 백테스트
│   └── results/                            # 백테스트 결과
│
├── run_tuning_backtest.sh                  # 실행 스크립트
├── QUICK_START_GUIDE.md                    # 이 문서
└── ARES7_SHARPE_2_5_TUNING_PLAN.md         # 상세 플랜
```

---

## 🎯 3가지 설정 비교

| 항목 | Conservative | Moderate | Aggressive |
|------|-------------|----------|------------|
| **목표 Sharpe** | 2.15 | 2.30 | 2.45 |
| **Max Leverage** | 1.5x | 2.0x | 2.5x |
| **Target Vol** | 8% | 10% | 12% |
| **VIX Guard** | 20+ (조기) | 25+ (표준) | 30+ (늦게) |
| **Overlay Strength** | 15% | 20% | 30% |
| **리스크** | 낮음 | 중간 | 높음 |
| **MDD 목표** | -10% | -12% | -15% |

### 추천 설정

- **처음 사용**: Conservative (안정성 우선)
- **검증 후**: Moderate (균형)
- **고급 사용자**: Aggressive (최대 성과)

---

## 📊 예상 결과

### Conservative (보수적)
```
Baseline (ARES7-Best)      Sharpe: 1.853  Return: 17.96%  MDD: -8.72%
+ Axis 1 (TC Model)        Sharpe: 1.903  (+0.05)
+ Axis 2 (Risk Scaler)     Sharpe: 2.003  (+0.10)
+ Axis 3 (QM Overlay)      Sharpe: 2.103  (+0.10)
+ Axis 4 (VIX Guard)       Sharpe: 2.153  (+0.05)
─────────────────────────────────────────────────────────
Combined (All Axes)        Sharpe: 2.15   (+0.30)  ✅
```

### Moderate (중간)
```
Baseline (ARES7-Best)      Sharpe: 1.853  Return: 17.96%  MDD: -8.72%
+ Axis 1 (TC Model)        Sharpe: 1.928  (+0.075)
+ Axis 2 (Risk Scaler)     Sharpe: 2.078  (+0.15)
+ Axis 3 (QM Overlay)      Sharpe: 2.228  (+0.15)
+ Axis 4 (VIX Guard)       Sharpe: 2.303  (+0.075)
─────────────────────────────────────────────────────────
Combined (All Axes)        Sharpe: 2.30   (+0.45)  ✅
```

### Aggressive (공격적)
```
Baseline (ARES7-Best)      Sharpe: 1.853  Return: 17.96%  MDD: -8.72%
+ Axis 1 (TC Model)        Sharpe: 1.953  (+0.10)
+ Axis 2 (Risk Scaler)     Sharpe: 2.153  (+0.20)
+ Axis 3 (QM Overlay)      Sharpe: 2.353  (+0.20)
+ Axis 4 (VIX Guard)       Sharpe: 2.453  (+0.10)
─────────────────────────────────────────────────────────
Combined (All Axes)        Sharpe: 2.45   (+0.60)  ✅
```

---

## 🔧 커스텀 설정

### Config 파일 수정

```yaml
# config/tuning_config_custom.yaml

# Axis 2: Risk Scaler 예시
risk_scaler:
  target_vol: 0.09        # 9% 변동성 (8%와 10% 사이)
  max_leverage: 1.8       # 1.8x 레버리지
  dd_threshold_1: -0.09   # -9% DD
  dd_reduction_1: 0.80    # 80%로 축소
```

### Python에서 직접 실행

```python
from tuning.backtest.ares7_tuning_backtest_v1 import ARES7TuningBacktest, TuningConfig
from risk.transaction_cost_model_v2 import TCCoeffs
from risk.global_risk_scaler import GlobalRiskConfig
# ... (imports)

# Custom config
config = TuningConfig(
    enable_tc_model=True,
    enable_risk_scaler=True,
    enable_qm_overlay=False,  # Overlay 비활성화
    enable_vix_guard=True,
    tc_coeffs=TCCoeffs(base_bps=2.0),
    risk_config=GlobalRiskConfig(target_vol=0.09, max_leverage=1.8),
)

# Run backtest
backtest = ARES7TuningBacktest(config)
results = backtest.run(
    base_returns=ares7_returns,
    base_weights=portfolio_weights,
    # ... (data)
)

backtest.print_results(results)
```

---

## 🐛 문제 해결

### 1. 데이터 오류
```
FileNotFoundError: 'ares7_best_returns.csv'
```
**해결**: 데이터 파일 경로 확인 및 준비

### 2. 모듈 임포트 오류
```
ModuleNotFoundError: No module named 'risk'
```
**해결**: 
```bash
cd ares7-ensemble
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

### 3. VIX 데이터 없음
```
VIX data not found
```
**해결**: 
- Yahoo Finance에서 다운로드: `^VIX`
- 또는 `modules/vix_global_guard.py`의 `load_vix_data()` 사용

### 4. 메모리 부족
```
MemoryError
```
**해결**:
- 백테스트 기간 축소 (2018-2024)
- 또는 서버/클라우드 사용

---

## 📈 결과 분석

### 백테스트 결과 파일

```bash
tuning/results/backtest_moderate_20251128_120000.txt
```

### 주요 지표 확인

```python
import pandas as pd

# 결과 로드
results = pd.read_csv('tuning/results/backtest_moderate_20251128_120000.txt')

# Sharpe 비교
print(f"Baseline Sharpe: {results['baseline']['sharpe']:.3f}")
print(f"Combined Sharpe: {results['combined']['sharpe']:.3f}")
print(f"Improvement: {results['combined']['sharpe'] - results['baseline']['sharpe']:.3f}")

# MDD 비교
print(f"Baseline MDD: {results['baseline']['max_dd']*100:.2f}%")
print(f"Combined MDD: {results['combined']['max_dd']*100:.2f}%")
```

### 시각화

```python
import matplotlib.pyplot as plt

# 누적 수익률 비교
plt.figure(figsize=(12, 6))
plt.plot((1 + results['baseline']['returns']).cumprod(), label='Baseline')
plt.plot((1 + results['combined']['returns']).cumprod(), label='Combined')
plt.legend()
plt.title('ARES7-Best: Baseline vs Tuned')
plt.xlabel('Date')
plt.ylabel('Cumulative Return')
plt.grid(True)
plt.savefig('tuning_results.png')
```

---

## 🎓 다음 단계

### 1주차: 검증
- [ ] Conservative 백테스트 실행
- [ ] 결과 분석 (Sharpe, MDD, Calmar)
- [ ] Out-of-sample 검증 (2021-2024)

### 2주차: 최적화
- [ ] Moderate 백테스트 실행
- [ ] 파라미터 그리드 서치
- [ ] 최적 설정 선택

### 3주차: 통합
- [ ] Aggressive 백테스트 실행
- [ ] 3가지 설정 비교
- [ ] 최종 설정 확정

### 4주차: 배포
- [ ] 프로덕션 코드 정리
- [ ] 모니터링 대시보드 구축
- [ ] 실거래 소액 테스트

---

## 📞 지원

### 문서
- [ARES7_SHARPE_2_5_TUNING_PLAN.md](ARES7_SHARPE_2_5_TUNING_PLAN.md): 상세 플랜
- [ML9_LAB_ENGINE.md](docs/ML9_LAB_ENGINE.md): ML9-Guard Lab 문서
- [ARES_X_V110_ARCHITECTURE_ANALYSIS.md](docs/ARES_X_V110_ARCHITECTURE_ANALYSIS.md): V110 분석

### 코드
- `risk/transaction_cost_model_v2.py`: TC Model 구현
- `risk/global_risk_scaler.py`: Risk Scaler 구현
- `modules/overlay_quality_mom_v1.py`: QM Overlay 구현
- `modules/vix_global_guard.py`: VIX Guard 구현

### GitHub
- ML9-Guard Lab: https://github.com/yhun1542/ml9-quant-strategy
- Tag: `lab-ml9-guard-v1`

---

## ✅ 체크리스트

시작 전 확인:
- [ ] 패키지 압축 해제 완료
- [ ] Python 3.8+ 설치 확인
- [ ] 필요한 라이브러리 설치 (pandas, numpy, matplotlib)
- [ ] ARES7-Best 데이터 준비
- [ ] VIX 데이터 준비
- [ ] SF1 펀더멘털 데이터 준비 (Axis 3용)

실행:
- [ ] Conservative 백테스트 완료
- [ ] Moderate 백테스트 완료
- [ ] Aggressive 백테스트 완료
- [ ] 결과 분석 완료

다음 단계:
- [ ] 최적 설정 선택
- [ ] Out-of-sample 검증
- [ ] 프로덕션 배포 준비

---

**작성일**: 2025-11-28  
**버전**: 1.0  
**상태**: ✅ 준비 완료

**시작하세요!** 🚀
```bash
./run_tuning_backtest.sh moderate
```
