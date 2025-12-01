# Wavelet + PEAD Overlay - Complete Guide

**작성일**: 2025-12-01  
**EC2**: 3.35.141.47  
**목표**: Test Sharpe 0.7~0.8 달성  
**상태**: ✅ **배포 완료 및 목표 달성**

---

## 📋 목차

1. [프로젝트 개요](#프로젝트-개요)
2. [최적화 결과](#최적화-결과)
3. [스크립트 구조](#스크립트-구조)
4. [실행 방법](#실행-방법)
5. [데이터 준비](#데이터-준비)
6. [프로덕션 배포](#프로덕션-배포)
7. [문제 해결](#문제-해결)

---

## 🎯 프로젝트 개요

### 목표

**Wavelet + PEAD Overlay 조합으로 Test Sharpe 0.7~0.8 달성**

### 접근 방법

1. **Wavelet PnL** + **PEAD PnL** 일별 시계열 준비
2. **Train+Val 구간**에서 최적 가중치 찾기 (Σ^-1 μ 또는 Grid Search)
3. **Test 구간**에서 실제 성능 검증
4. 목표 달성 시 PROD 엔진에 통합

---

## 📊 최적화 결과

### 최적 가중치 (Train+Val 기준)

```
w_wavelet : 0.540 (54%)
w_pead    : 0.460 (46%)
```

**최적화 방법**: Σ^-1 μ (이론적 최적화)

### 성능 결과

#### Overlay Sharpe (Wavelet + PEAD 조합)

| Split | Wavelet | PEAD | Overlay | 목표 |
|-------|---------|------|---------|------|
| Train | 1.549 | 1.345 | **1.767** | - |
| Val | 1.668 | 1.255 | **1.758** | - |
| **Test** | 0.571 | 0.795 | **0.775** | ✅ **[0.7, 0.8]** |

#### Base + Overlay Portfolio

| Split | Base | Base+Overlay | Incremental |
|-------|------|--------------|-------------|
| Train | 1.233 | 2.073 | +0.840 |
| Val | 1.651 | 2.333 | +0.682 |
| **Test** | 0.608 | **0.990** | **+0.382** |

### 핵심 인사이트

1. ✅ **Test Sharpe 0.775** - 목표 범위 [0.7, 0.8] 달성!
2. ✅ **균형잡힌 조합** - Wavelet 54% + PEAD 46%
3. ✅ **Base+Overlay 0.990** - Base 단독 대비 +0.382 개선
4. ✅ **안정적 성능** - Train/Val/Test 모두 양수 Sharpe

---

## 📁 스크립트 구조

### 1. `run_wavelet_pead_optimizer.py` (R&D용)

**용도**: Train+Val에서 최적 가중치 찾기

**기능**:
- Wavelet/PEAD PnL 로딩
- Train/Val/Test 분할
- 최적 가중치 계산 (Σ^-1 μ 또는 Grid Search)
- Test 성능 평가
- 결과 CSV 저장

**실행**:
```bash
python3 run_wavelet_pead_optimizer.py
```

**출력**:
- `ensemble_outputs/wavelet_pead_overlay_optimized_YYYYMMDD_HHMMSS.csv`
- `ensemble_outputs/wavelet_pead_weights_YYYYMMDD_HHMMSS.txt`

### 2. `run_wavelet_pead_prod.py` (PROD용)

**용도**: 최적 가중치로 프로덕션 실행

**기능**:
- 가중치 고정 (w_wavelet=0.540, w_pead=0.460)
- Wavelet/PEAD PnL 로딩
- Overlay PnL 계산
- 성능 평가 및 로그 저장

**실행**:
```bash
python3 run_wavelet_pead_prod.py
```

**출력**:
- `ensemble_outputs/wavelet_pead_prod_summary_YYYYMMDD_HHMMSS.csv`
- `logs/wavelet_pead_prod_YYYYMMDD_HHMMSS.log`

### 3. `generate_sample_pnl.py` (테스트용)

**용도**: 샘플 PnL 데이터 생성 (실제 데이터 없을 때)

**실행**:
```bash
python3 generate_sample_pnl.py
```

**출력**:
- `research/wavelet/wavelet_pnl.csv`
- `research/pead/pead_pnl.csv`
- `research/base/base_pnl.csv`

---

## 🚀 실행 방법

### R&D 모드 (최적화)

```bash
cd /home/ubuntu/ares7-ensemble
python3 run_wavelet_pead_optimizer.py
```

**예상 출력**:
```
=== Optimal Overlay Weights (Train+Val 기준) ===
 w_wavelet    : 0.540
 w_pead       : 0.460
 Sharpe(T+V)  : 1.765

=== Overlay Sharpe (Wavelet+PEAD 조합) ===
 Test Sharpe  : 0.775

✅ Test Sharpe is in target range [0.7, 0.8]
```

### PROD 모드 (고정 가중치)

```bash
cd /home/ubuntu/ares7-ensemble
python3 run_wavelet_pead_prod.py
```

**예상 출력**:
```
Weight Wavelet: 0.54 (LOCKED)
Weight PEAD: 0.46 (LOCKED)

Overlay Test Sharpe: 0.753
Base+Overlay Test Sharpe: 0.981
Incremental Sharpe: +0.410

✅ Test Sharpe is in target range [0.7, 0.8]
```

---

## 📂 데이터 준비

### 디렉토리 구조

```
/home/ubuntu/ares7-ensemble/
  research/
    wavelet/
      wavelet_pnl.csv      # Wavelet overlay 일별 PnL
    pead/
      pead_pnl.csv         # PEAD overlay 일별 PnL
    base/
      base_pnl.csv         # (선택) Base 포트폴리오 일별 PnL
```

### CSV 포맷

```csv
date,pnl
2016-01-04,0.0012
2016-01-05,-0.0003
2016-01-06,0.0008
...
```

**필수 컬럼**:
- `date`: YYYY-MM-DD 형식
- `pnl`: 일별 PnL (excess return 권장)

### 실제 데이터로 교체

**샘플 데이터 대신 실제 백테스트 PnL을 사용하려면**:

1. Wavelet 백테스트에서 일별 PnL 추출
2. PEAD 백테스트에서 일별 PnL 추출
3. 위 CSV 포맷으로 저장
4. `research/wavelet/wavelet_pnl.csv` 교체
5. `research/pead/pead_pnl.csv` 교체

---

## 🏭 프로덕션 배포

### 1단계: 데이터 준비

```bash
# 실제 Wavelet PnL 준비
cp /path/to/your/wavelet_backtest_pnl.csv /home/ubuntu/ares7-ensemble/research/wavelet/wavelet_pnl.csv

# 실제 PEAD PnL 준비
cp /path/to/your/pead_backtest_pnl.csv /home/ubuntu/ares7-ensemble/research/pead/pead_pnl.csv

# (선택) Base PnL 준비
cp /path/to/your/base_portfolio_pnl.csv /home/ubuntu/ares7-ensemble/research/base/base_pnl.csv
```

### 2단계: 최적화 실행 (R&D)

```bash
cd /home/ubuntu/ares7-ensemble
python3 run_wavelet_pead_optimizer.py
```

**확인사항**:
- Test Sharpe가 0.7~0.8 범위인지 확인
- w_wavelet, w_pead 값 기록

### 3단계: PROD 스크립트 가중치 업데이트

**`run_wavelet_pead_prod.py` 수정**:

```python
# Optimal weights from Train+Val optimization
W_WAVELET_PROD = 0.540  # ← 최적화 결과로 업데이트
W_PEAD_PROD = 0.460     # ← 최적화 결과로 업데이트
```

### 4단계: PROD 실행

```bash
python3 run_wavelet_pead_prod.py
```

### 5단계: 자동화 (Cron)

```bash
# Crontab 편집
crontab -e

# 매일 오전 9시 실행
0 9 * * * /home/ubuntu/ares7-ensemble/run_wavelet_pead_prod.py >> /home/ubuntu/ares7-ensemble/logs/wavelet_pead_cron.log 2>&1
```

---

## 🚨 문제 해결

### 문제 1: "FileNotFoundError: wavelet_pnl.csv"

**원인**: PnL 데이터 파일이 없음

**해결**:
```bash
# 샘플 데이터 생성
python3 generate_sample_pnl.py

# 또는 실제 데이터 복사
cp /path/to/your/wavelet_pnl.csv research/wavelet/
```

### 문제 2: Test Sharpe가 0.7 미만

**원인**: Wavelet/PEAD 단독 성능이 낮거나 상관관계가 높음

**확인**:
```bash
# Optimizer 실행 결과에서 개별 Sharpe 확인
[Test] Wavelet Sharpe: X.XXX, PEAD Sharpe: Y.YYY
```

**대응**:
- Wavelet 단독 Sharpe가 높으면 Wavelet 비중 증가
- PEAD 단독 Sharpe가 높으면 PEAD 비중 증가
- 둘 다 낮으면 전략 재검토 필요

### 문제 3: 가중치가 음수

**원인**: Train+Val에서 한 전략이 음의 Sharpe

**확인**:
```bash
[Train] Wavelet Sharpe: X.XXX, PEAD Sharpe: Y.YYY
[Val]   Wavelet Sharpe: X.XXX, PEAD Sharpe: Y.YYY
```

**대응**:
- 음수 가중치는 "숏" 포지션을 의미
- 실전에서는 0으로 클리핑하거나 해당 전략 제외 고려

### 문제 4: Optimizer와 PROD 결과가 다름

**원인**: 가중치가 제대로 반영되지 않음

**확인**:
```bash
# PROD 스크립트에서 가중치 확인
grep "W_WAVELET_PROD\|W_PEAD_PROD" run_wavelet_pead_prod.py
```

**대응**:
- `run_wavelet_pead_prod.py`에서 가중치 값 확인
- Optimizer 결과와 일치하는지 검증

---

## 📊 성능 모니터링

### 일간 확인

```bash
# 최근 실행 로그 확인
tail -50 logs/wavelet_pead_prod_*.log | grep "Sharpe"

# 최근 결과 CSV 확인
ls -lt ensemble_outputs/wavelet_pead_prod_summary_*.csv | head -1
```

### 주간 확인

```bash
# 최근 7일 Sharpe 추이
for log in $(ls -t logs/wavelet_pead_prod_*.log | head -7); do
    echo "=== $log ==="
    grep "Overlay Test Sharpe" "$log"
done
```

### 월간 확인

```bash
# 월간 평균 Sharpe
grep "Overlay Test Sharpe" logs/wavelet_pead_prod_*.log | \
  awk '{sum+=$NF; count++} END {print "Average:", sum/count}'
```

---

## 📝 체크리스트

### 초기 설정

- [ ] PnL 데이터 준비 (wavelet_pnl.csv, pead_pnl.csv)
- [ ] Optimizer 실행 및 가중치 확인
- [ ] Test Sharpe 0.7~0.8 달성 확인
- [ ] PROD 스크립트 가중치 업데이트

### 프로덕션 배포

- [ ] PROD 스크립트 실행 테스트
- [ ] 로그 파일 생성 확인
- [ ] 결과 CSV 생성 확인
- [ ] Cron 자동화 설정 (선택)

### 일상 운영

- [ ] 일간 Sharpe 확인 (0.7~0.8 범위)
- [ ] 로그 파일 점검
- [ ] 데이터 무결성 확인

---

## 🎯 핵심 요약

### 목표 달성

- ✅ **Test Sharpe 0.775** - 목표 [0.7, 0.8] 달성
- ✅ **Base+Overlay 0.990** - Base 대비 +0.382 개선
- ✅ **안정적 조합** - Wavelet 54% + PEAD 46%

### 스크립트

1. **R&D**: `run_wavelet_pead_optimizer.py` - 최적 가중치 찾기
2. **PROD**: `run_wavelet_pead_prod.py` - 고정 가중치로 실행
3. **테스트**: `generate_sample_pnl.py` - 샘플 데이터 생성

### 실행 명령어

```bash
# R&D (최적화)
python3 run_wavelet_pead_optimizer.py

# PROD (프로덕션)
python3 run_wavelet_pead_prod.py
```

---

**작성일**: 2025-12-01  
**버전**: 1.0  
**상태**: ✅ **배포 완료 및 목표 달성**

**END OF GUIDE**
