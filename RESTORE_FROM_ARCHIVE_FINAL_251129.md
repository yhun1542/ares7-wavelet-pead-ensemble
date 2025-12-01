# ARES7 QM Regime Turbo 복원 가이드

이 문서는 `ares7_qm_regime_final_251129_full.tar.gz` 아카이브에서 ARES7 QM Regime Turbo 전략 전체를 복원하는 방법을 설명합니다.

## 📦 아카이브 정보

- **파일명**: `ares7_qm_regime_final_251129_full.tar.gz`
- **생성일**: 2025-11-29
- **태그**: `ares7_qm_regime_turbo_final_251129`
- **최종 성능**:
  - Sharpe Ratio: **3.86**
  - OOS Sharpe: **4.37**
  - 연율화 수익률: **67.74%**
  - MDD: **-12.63%**
  - OOS MDD: **-10.10%**

## 1. 아카이브 풀기

```bash
# 작업 디렉토리 생성
mkdir ares7_qm_regime_final_251129
cd ares7_qm_regime_final_251129

# 아카이브 압축 해제
tar -xzf /path/to/ares7_qm_regime_final_251129_full.tar.gz

# 디렉토리 구조 확인
tree -L 2 -d
```

## 2. Python 환경 준비

```bash
# 가상환경 생성
python3 -m venv .venv

# 가상환경 활성화
source .venv/bin/activate  # Linux/Mac
# Windows의 경우: .venv\Scripts\activate

# 필수 패키지 설치
pip install --upgrade pip
pip install pandas numpy scipy numba matplotlib seaborn
```

### 필수 패키지 목록

- **pandas**: 데이터 처리
- **numpy**: 수치 계산
- **scipy**: 통계 분석
- **numba**: JIT 컴파일 (성능 최적화)
- **matplotlib, seaborn**: 시각화

## 3. 데이터 파일 확인

아카이브에는 다음 데이터 파일들이 포함되어 있습니다:

```bash
data/
├── prices.csv                    # 가격 데이터
├── bull_regime.csv              # Bull 레짐 신호
├── bear_regime.csv              # Bear 레짐 신호
└── neutral_regime.csv           # Neutral 레짐 신호
```

데이터 파일이 정상적으로 존재하는지 확인:

```bash
ls -lh data/*.csv
```

## 4. 최종 백테스트 재실행

### 4.1. Turbo Grid Search 재실행

```bash
# Turbo Grid Search 실행 (약 10초 소요)
python3 turbo_grid_search.py
```

**예상 출력**:
```
Grid Search 완료: 5400개 조합 탐색
최적 파라미터:
  - base_leverage: 1.2
  - max_leverage: 1.8
  - target_volatility: 0.18
  - cb_trigger: -0.06
  - cb_reduction_factor: 0.4

최종 성능:
  - Full Sharpe: 3.86
  - OOS Sharpe: 4.37
  - Full MDD: -12.63%
  - OOS MDD: -10.10%
```

### 4.2. 결과 파일 확인

백테스트 완료 후 다음 파일들이 생성됩니다:

```bash
results/
├── turbo_grid_search_results.json      # 그리드 서치 결과
├── ensemble_returns_turbo_optimized.csv # 최적화된 수익률
└── performance_comparison.png           # 성능 비교 차트
```

## 5. 결과 검증

### 5.1. 성능 지표 확인

```bash
python3 << 'PYEOF'
import json

with open('results/turbo_grid_search_results.json', 'r') as f:
    results = json.load(f)

print("=== 최종 성능 검증 ===")
print(f"Full Sharpe: {results['performance_full']['sharpe']:.2f}")
print(f"OOS Sharpe: {results['performance_test']['sharpe']:.2f}")
print(f"Full Return: {results['performance_full']['return']:.2%}")
print(f"Full MDD: {results['performance_full']['mdd']:.2%}")
print(f"OOS MDD: {results['performance_test']['mdd']:.2%}")
PYEOF
```

**예상 출력**:
```
=== 최종 성능 검증 ===
Full Sharpe: 3.86
OOS Sharpe: 4.37
Full Return: 67.74%
Full MDD: -12.63%
OOS MDD: -10.10%
```

### 5.2. 룩어헤드 바이어스 검증

```bash
python3 verify_lookahead_bias.py
```

모든 검증 항목이 통과해야 합니다:
- ✓ 룩어헤드 바이어스: 없음
- ✓ 과적합성: 없음
- ✓ 거래 비용: 반영됨
- ✓ 데이터 분할: 적절

## 6. 주요 구성 요소

### 6.1. 엔진 (engines/)

- `low_volatility_v2.py`: Low Volatility Enhanced Engine

### 6.2. 앙상블 (ensemble/)

- `dynamic_ensemble_v2.py`: Dynamic Ensemble v2
- `weight_optimizer_cvar.py`: CVaR Weight Optimizer

### 6.3. 리스크 관리 (risk/)

- `adaptive_asymmetric_risk_manager.py`: AARM (핵심 리스크 관리)
- `enhanced_aarm.py`: Enhanced AARM
- `mdd_improvement.py`: MDD 개선 모듈

### 6.4. 최적화 스크립트

- `turbo_grid_search.py`: CPU 최적화된 그리드 서치 (Numba JIT)
- `run_weight_optimization.py`: 가중치 최적화
- `run_real_data_backtest_v2.py`: 실제 데이터 백테스트

## 7. Manus에게 복원 지시 템플릿

ChatGPT 또는 Manus에게 다음과 같이 지시하면 됩니다:

```
"이 아카이브 ares7_qm_regime_final_251129_full.tar.gz를 기준으로
ARES7 QM Regime Turbo 전략 전체를 복원하고,
turbo_grid_search.py를 실행해서 최종 백테스트 결과를 다시 만들어줘.

예상 결과:
- Sharpe Ratio: 3.86
- OOS Sharpe: 4.37
- MDD: -12.63%
- OOS MDD: -10.10%

모든 검증 항목(룩어헤드 바이어스, 과적합성, 거래 비용)이 통과하는지 확인해줘."
```

## 8. 트러블슈팅

### 문제: Numba 설치 실패

```bash
# Numba 없이도 실행 가능하도록 코드가 작성되어 있음
# 단, 속도가 느려질 수 있음
python3 turbo_grid_search.py  # Numba 없이도 작동
```

### 문제: 데이터 파일 없음

```bash
# 데이터 파일이 없으면 다음 스크립트로 재생성
python3 download_spy_tlt.py  # SPY/TLT 데이터 다운로드
```

### 문제: 결과가 다름

- 데이터 기간이 다를 수 있음 (최신 데이터 추가)
- 난수 시드 차이 (그리드 서치는 결정론적이므로 동일해야 함)
- Python 버전 차이 (Python 3.8+ 권장)

## 9. 추가 분석

### 9.1. 성능 비교 차트 생성

```bash
python3 << 'PYEOF'
import pandas as pd
import matplotlib.pyplot as plt

# 수익률 데이터 로드
returns = pd.read_csv('results/ensemble_returns_turbo_optimized.csv', 
                      index_col=0, parse_dates=True)

# 누적 수익률 계산
cum_returns = (1 + returns).cumprod()

# 차트 생성
plt.figure(figsize=(12, 6))
plt.plot(cum_returns.index, cum_returns.values, label='ARES7 Turbo')
plt.title('ARES7 QM Regime Turbo - Cumulative Returns')
plt.xlabel('Date')
plt.ylabel('Cumulative Return')
plt.legend()
plt.grid(True)
plt.savefig('results/cumulative_returns.png', dpi=300)
print("차트 저장: results/cumulative_returns.png")
PYEOF
```

### 9.2. 월별 성과 분석

```bash
python3 << 'PYEOF'
import pandas as pd

returns = pd.read_csv('results/ensemble_returns_turbo_optimized.csv', 
                      index_col=0, parse_dates=True)

# 월별 수익률
monthly = returns.resample('M').apply(lambda x: (1 + x).prod() - 1)

print("=== 월별 수익률 통계 ===")
print(f"평균: {monthly.mean():.2%}")
print(f"중앙값: {monthly.median():.2%}")
print(f"최고: {monthly.max():.2%}")
print(f"최저: {monthly.min():.2%}")
print(f"승률: {(monthly > 0).mean():.1%}")
PYEOF
```

## 10. 시스템 요구사항

- **OS**: Linux, macOS, Windows
- **Python**: 3.8 이상
- **RAM**: 최소 4GB (권장 8GB)
- **CPU**: 멀티코어 권장 (Turbo Grid Search 최적화)
- **디스크**: 최소 500MB

## 11. 라이선스 및 면책

이 시스템은 연구 및 교육 목적으로 제공됩니다. 실제 거래에 사용하기 전에 충분한 검증과 리스크 관리가 필요합니다.

---

**문의**: 복원 과정에서 문제가 발생하면 이 문서를 참조하거나, Manus에게 이 문서와 함께 질문하세요.

**최종 업데이트**: 2025-11-29
