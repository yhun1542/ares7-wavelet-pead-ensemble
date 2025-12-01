# ARES8 Wrapper Scripts - Quick Start Guide

**빠른 실행 가이드** | 2025-12-01

---

## 🚀 5분 안에 시작하기

### 1️⃣ Buyback R&D 분석 (단독)

```bash
cd /home/ubuntu/ares7-ensemble
python3.11 run_buyback_v2_real.py
```

**출력**:
- 콘솔: Split × Horizon별 Sharpe, t-stat, win rate
- CSV: `buyback_v2_outputs/summary_v2.csv`, `shuffle_v2.csv`

**예상 결과**:
```
Test 30d: n=67, sharpe=0.113, p_value=1.0
→ 통계적 유의성 없음
```

---

### 2️⃣ PEAD+Buyback 앙상블 분석

#### PRODUCTION 모드 (PEAD Only)

```bash
cd /home/ubuntu/ares7-ensemble
python3.11 run_pead_buyback_ensemble.py
```

**출력**:
- 콘솔: 4가지 전략 비교 (Base/PEAD/Buyback/Ensemble)
- CSV: `ensemble_outputs/ensemble_summary.csv`

**예상 결과**:
```
PEAD Test Sharpe: 0.504
Ensemble Test Sharpe: 0.504
→ Ensemble == PEAD (α_bb=0.0)
```

#### R&D 모드 (PEAD+Buyback)

1. **파일 수정**: `run_pead_buyback_ensemble.py` 55-65행
   ```python
   # 주석 해제
   ALPHA_PEAD = 0.6
   ALPHA_BB = 0.4
   ```

2. **실행**:
   ```bash
   python3.11 run_pead_buyback_ensemble.py
   ```

**예상 결과**:
```
PEAD Test Sharpe: 0.504
Ensemble Test Sharpe: 0.510
→ Ensemble vs PEAD: +0.006 Sharpe
```

---

## 📋 필수 데이터 파일

```
data/
├── buyback_events.csv          # 260 events
├── prices.csv                  # 100 tickers, 2512 days
├── pead_event_table_positive.csv  # 901 events
└── ares7_base_weights.csv      # 243,151 records
```

**확인 명령**:
```bash
ls -lh data/*.csv | grep -E "(buyback_events|prices|pead_event|ares7_base)"
```

---

## 🎯 주요 파라미터

### Buyback R&D (`run_buyback_v2_real.py`)
- **Horizons**: [10, 20, 30, 40] days
- **N_Shuffles**: 100
- **Split**: Train(2016-2018), Val(2019-2021), Test(2022-2025)

### Ensemble (`run_pead_buyback_ensemble.py`)
- **PRODUCTION**: α_pead=1.0, α_bb=0.0
- **R&D**: α_pead=0.6, α_bb=0.4
- **Tilt Size**: 1.5%p
- **Horizon**: 30 days

---

## 🔧 트러블슈팅

### 문제 1: "No module named 'research.pead'"
**해결**:
```bash
cd /home/ubuntu/ares7-ensemble
export PYTHONPATH=/home/ubuntu/ares7-ensemble:$PYTHONPATH
```

### 문제 2: "FileNotFoundError: data/prices.csv"
**해결**:
```bash
# 데이터 파일 복사
cp /home/ubuntu/upload/*.csv data/
```

### 문제 3: "KeyError: 'weighted_rank'"
**해결**: 최신 버전 사용 (2025-12-01 이후)

---

## 📊 결과 해석

### Buyback R&D 결과

| 지표 | 의미 | 기준 |
|------|------|------|
| **Sharpe** | 위험 대비 수익률 | > 0.5 (강함) |
| **t_stat** | 통계적 유의성 | > 2.0 (유의) |
| **p_value** | Label shuffle 검증 | < 0.05 (유의) |

**현재 Buyback**:
- Test Sharpe: 0.113 ❌
- t_stat: 0.92 ❌
- p_value: 1.0 ❌
- **결론**: 통계적 유의성 없음

### Ensemble 결과

| 전략 | Test Sharpe | Incremental |
|------|-------------|-------------|
| Base | 0.451 | - |
| PEAD | 0.504 | +0.053 ✅ |
| Buyback | 0.113 | -0.338 ❌ |
| Ensemble (PEAD Only) | 0.504 | +0.053 ✅ |

**결론**: PEAD Only가 최적

---

## 🎓 다음 단계

### 프로덕션 배포
1. `run_pead_buyback_ensemble.py` PRODUCTION 모드 확인
2. Test 실행하여 Sharpe 0.504 확인
3. ARES7 시스템에 통합

### R&D 실험
1. Buyback 시그널 개선 (NBY 외 피처 추가)
2. 다른 이벤트 타입 탐색 (Insider Trading, M&A)
3. 가중치 최적화 (Grid Search)

---

## 📚 관련 문서

- **상세 문서**: `WRAPPER_SCRIPTS_README.md`
- **프로젝트 보고서**: `FINAL_PROJECT_REPORT.md`
- **AI 피드백**: `AI_FEEDBACK_SYNTHESIS.md`

---

**Happy Trading! 🚀**
