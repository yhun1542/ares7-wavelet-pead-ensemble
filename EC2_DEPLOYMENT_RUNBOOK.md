# ARES8 EC2 Deployment & Operations Runbook

**작성일**: 2025-12-01  
**대상 환경**: EC2 (3.35.141.47)  
**프로덕션 전략**: PEAD Only Overlay (Buyback Disabled)  
**버전**: 1.0

---

## 📋 목차

1. [EC2 디렉토리 구조](#ec2-디렉토리-구조)
2. [프로덕션 실행 커맨드](#프로덕션-실행-커맨드)
3. [R&D 실행 커맨드](#rd-실행-커맨드)
4. [안전장치 설계](#안전장치-설계)
5. [운영 체크리스트](#운영-체크리스트)
6. [장애 대응 가이드](#장애-대응-가이드)
7. [로그 관리](#로그-관리)
8. [자동화 설정](#자동화-설정)

---

## 📁 EC2 디렉토리 구조

```
/home/ubuntu/ares7-ensemble/
├── run_pead_buyback_ensemble_prod.py    # PRODUCTION 스크립트 (PEAD Only)
├── run_buyback_v2_real.py               # R&D 스크립트 (Buyback 연구용)
├── data/
│   ├── buyback_events.csv               # Buyback 이벤트 (260 → 175 필터링)
│   ├── prices.csv                       # 가격 데이터 (100 tickers, 2512 days)
│   ├── pead_event_table_positive.csv    # PEAD 이벤트 (901개)
│   └── ares7_base_weights.csv           # Base 포트폴리오 (Vol-weighted)
├── research/pead/
│   ├── event_book.py                    # Pure Tilt 엔진
│   └── forward_return.py                # Forward return 계산
├── logs/
│   └── ensemble_prod_YYYYMMDD_HHMMSS.log  # 실행 로그
├── ensemble_outputs/
│   └── ensemble_summary_prod_YYYYMMDD_HHMMSS.csv  # 결과 CSV
└── buyback_v2_outputs/
    ├── summary_v2.csv                   # Buyback 연구 결과
    └── shuffle_v2.csv                   # Label shuffle 검증
```

---

## 🚀 프로덕션 실행 커맨드

### 기본 실행 (PEAD Only)

```bash
cd /home/ubuntu/ares7-ensemble
python3 run_pead_buyback_ensemble_prod.py
```

**예상 출력**:
```
================================================================================
✅ PRODUCTION MODE
================================================================================
PEAD Only Overlay (Buyback Disabled)
================================================================================
Alpha PEAD: 1.0
Alpha Buyback: 0.0 (LOCKED)
================================================================================
...
Base Test Sharpe: 0.451
Overlay Test Sharpe: 0.504
Incremental Sharpe: +0.053

✅ PRODUCTION MODE: PEAD Only (Buyback weight = 0)
   Strategy is ready for production deployment
```

### 환경변수 확인

```bash
# PRODUCTION 모드 확인 (기본값)
echo $ENABLE_RD_MODE
# 출력: (비어있음) 또는 0

# 프로덕션 모드 명시적 설정
export ENABLE_RD_MODE=0
python3 run_pead_buyback_ensemble_prod.py
```

### 백그라운드 실행

```bash
# nohup으로 백그라운드 실행
nohup python3 run_pead_buyback_ensemble_prod.py > /tmp/ares8_prod.log 2>&1 &

# 실행 확인
tail -f /tmp/ares8_prod.log
```

---

## 🔬 R&D 실행 커맨드

### Buyback 단독 연구

```bash
cd /home/ubuntu/ares7-ensemble
python3 run_buyback_v2_real.py
```

**⚠️ 경고**:
- 이 스크립트는 **연구 목적**으로만 사용
- 프로덕션 파이프라인에 **절대 연결 금지**
- 자동화 스케줄링 **금지**

### PEAD+Buyback 앙상블 (R&D 모드)

```bash
# R&D 모드 활성화
export ENABLE_RD_MODE=1
python3 run_pead_buyback_ensemble_prod.py
```

**예상 출력**:
```
================================================================================
⚠️  WARNING: R&D MODE ENABLED
================================================================================
This mode allows Buyback overlay for research purposes.
DO NOT use this mode in production deployment!
================================================================================
Alpha PEAD: 0.6
Alpha Buyback: 0.4 (R&D Mode)
...
⚠️  R&D MODE: PEAD + Buyback (α_bb=0.4)
   DO NOT deploy this configuration to production!
```

**⚠️ 주의사항**:
- R&D 모드는 **실험용**으로만 사용
- 프로덕션 배포 시 반드시 `ENABLE_RD_MODE=0` 확인
- R&D 실행 후 환경변수 초기화: `unset ENABLE_RD_MODE`

---

## 🔒 안전장치 설계

### 1. 환경변수 기반 모드 제어

```python
# run_pead_buyback_ensemble_prod.py 내부
ENABLE_RD_MODE = os.getenv("ENABLE_RD_MODE", "0") == "1"

if ENABLE_RD_MODE:
    MODE = "RD"
    # R&D 모드 경고 출력
else:
    MODE = "PROD"
    # PRODUCTION 모드 확인
```

**안전장치**:
- 환경변수가 없거나 "0"이면 자동으로 PRODUCTION 모드
- R&D 모드는 명시적으로 `ENABLE_RD_MODE=1` 설정 필요

### 2. 코드 레벨 α_bb 강제

```python
# PRODUCTION 모드에서 α_bb를 강제로 0.0으로 고정
if MODE == "PROD":
    ALPHA_PEAD = ALPHA_PEAD_PROD  # 1.0
    ALPHA_BB = ALPHA_BB_PROD      # 0.0
    
    # CRITICAL: 코드 레벨 방어
    ALPHA_BB = 0.0  # DO NOT MODIFY IN PRODUCTION
```

**안전장치**:
- PRODUCTION 모드에서는 α_bb를 두 번 0.0으로 설정
- 코드 수정 실수 방지

### 3. 실행 시 모드 확인 메시지

```
✅ PRODUCTION MODE
PEAD Only Overlay (Buyback Disabled)
Alpha Buyback: 0.0 (LOCKED)
```

**안전장치**:
- 실행 시 즉시 모드 확인 가능
- "LOCKED" 표시로 변경 불가 명시

### 4. 로그 파일 자동 생성

```python
LOG_FILE = LOG_DIR / f"ensemble_{MODE.lower()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
```

**안전장치**:
- 모든 실행이 로그로 기록됨
- 모드별 로그 파일 분리 (prod/rd)
- 타임스탬프로 실행 이력 추적

---

## ✅ 운영 체크리스트

### 배포 전 확인사항

- [ ] EC2 접속 확인: `ssh -i kimera1023.pem ubuntu@3.35.141.47`
- [ ] 디렉토리 구조 확인: `ls -la /home/ubuntu/ares7-ensemble/`
- [ ] 데이터 파일 존재 확인: `ls -lh /home/ubuntu/ares7-ensemble/data/*.csv`
- [ ] Python 버전 확인: `python3 --version` (3.12.3)
- [ ] 환경변수 확인: `echo $ENABLE_RD_MODE` (비어있거나 0)
- [ ] 스크립트 실행 권한 확인: `ls -l run_pead_buyback_ensemble_prod.py`

### 실행 전 확인사항

- [ ] PRODUCTION 모드 확인: `ENABLE_RD_MODE` 미설정 또는 0
- [ ] 디스크 공간 확인: `df -h /home/ubuntu/ares7-ensemble/`
- [ ] 로그 디렉토리 확인: `ls -la /home/ubuntu/ares7-ensemble/logs/`
- [ ] 이전 실행 로그 확인: `tail -50 logs/ensemble_prod_*.log | head -20`

### 실행 후 확인사항

- [ ] 실행 완료 메시지 확인: "ENSEMBLE ANALYSIS COMPLETE"
- [ ] Test Sharpe 확인: 0.504 (±0.05 범위)
- [ ] Incremental Sharpe 확인: +0.053 (±0.02 범위)
- [ ] 결과 CSV 생성 확인: `ls -lt ensemble_outputs/ensemble_summary_prod_*.csv | head -1`
- [ ] 로그 파일 확인: `tail -20 logs/ensemble_prod_*.log`
- [ ] α_bb=0.0 확인: 로그에서 "Alpha Buyback: 0.0" 검색

---

## 🚨 장애 대응 가이드

### 문제 1: "No module named 'research.pead'"

**증상**:
```
ModuleNotFoundError: No module named 'research.pead'
```

**원인**: Python 경로 문제

**해결**:
```bash
cd /home/ubuntu/ares7-ensemble
export PYTHONPATH=/home/ubuntu/ares7-ensemble:$PYTHONPATH
python3 run_pead_buyback_ensemble_prod.py
```

**영구 해결**:
```bash
echo 'export PYTHONPATH=/home/ubuntu/ares7-ensemble:$PYTHONPATH' >> ~/.bashrc
source ~/.bashrc
```

### 문제 2: "FileNotFoundError: data/prices.csv"

**증상**:
```
FileNotFoundError: [Errno 2] No such file or directory: 'data/prices.csv'
```

**원인**: 데이터 파일 누락

**해결**:
```bash
# 데이터 파일 확인
ls -lh /home/ubuntu/ares7-ensemble/data/

# 파일이 없으면 재전송 필요
# (로컬에서) scp -i kimera1023.pem data/*.csv ubuntu@3.35.141.47:/home/ubuntu/ares7-ensemble/data/
```

### 문제 3: Sharpe 비정상 (< 0.4 또는 > 0.6)

**증상**:
```
Overlay Test Sharpe: 0.234  # 너무 낮음
```

**원인**: 데이터 오류 또는 코드 변경

**확인 순서**:
1. 데이터 파일 무결성 확인:
   ```bash
   wc -l data/*.csv
   # buyback_events.csv: 261 lines
   # prices.csv: 247190 lines
   # pead_event_table_positive.csv: 902 lines
   # ares7_base_weights.csv: 243152 lines
   ```

2. α_bb 값 확인:
   ```bash
   grep "Alpha Buyback" logs/ensemble_prod_*.log | tail -1
   # 출력: Alpha Buyback: 0.0 (예상)
   ```

3. 모드 확인:
   ```bash
   grep "MODE" logs/ensemble_prod_*.log | tail -1
   # 출력: PROD MODE (예상)
   ```

4. 코드 변경 여부 확인:
   ```bash
   md5sum run_pead_buyback_ensemble_prod.py
   # 원본과 비교
   ```

### 문제 4: R&D 모드가 프로덕션에서 실행됨

**증상**:
```
⚠️  WARNING: R&D MODE ENABLED
Alpha Buyback: 0.4
```

**원인**: 환경변수 설정 오류

**즉시 조치**:
```bash
# 프로세스 중단
pkill -f run_pead_buyback_ensemble_prod.py

# 환경변수 초기화
unset ENABLE_RD_MODE

# PRODUCTION 모드로 재실행
python3 run_pead_buyback_ensemble_prod.py
```

**근본 원인 파악**:
```bash
# 환경변수 설정 확인
env | grep ENABLE_RD_MODE

# .bashrc 또는 .bash_profile 확인
grep ENABLE_RD_MODE ~/.bashrc ~/.bash_profile
```

---

## 📊 로그 관리

### 로그 파일 위치

```
/home/ubuntu/ares7-ensemble/logs/
├── ensemble_prod_20251201_150931.log
├── ensemble_prod_20251202_093045.log
└── ensemble_rd_20251201_161523.log  # R&D 실행 시
```

### 로그 확인 명령어

```bash
# 최신 PRODUCTION 로그 확인
tail -50 logs/ensemble_prod_*.log | tail -50

# 특정 날짜 로그 확인
ls -lt logs/ensemble_prod_20251201_*.log

# 에러 검색
grep -i "error\|exception\|warning" logs/ensemble_prod_*.log

# Sharpe 결과 검색
grep "Sharpe" logs/ensemble_prod_*.log | tail -5

# α_bb 값 검색
grep "Alpha Buyback" logs/ensemble_prod_*.log | tail -1
```

### 로그 회전 (Rotation)

**수동 정리** (월 1회 권장):
```bash
# 30일 이상 된 로그 삭제
find /home/ubuntu/ares7-ensemble/logs/ -name "ensemble_*.log" -mtime +30 -delete

# 로그 압축 보관
tar -czf logs_archive_$(date +%Y%m).tar.gz logs/ensemble_*.log
mv logs_archive_*.tar.gz /home/ubuntu/ares7-ensemble/logs_archive/
```

**자동 정리** (cron 설정):
```bash
# crontab -e
# 매월 1일 오전 2시에 30일 이상 된 로그 삭제
0 2 1 * * find /home/ubuntu/ares7-ensemble/logs/ -name "ensemble_*.log" -mtime +30 -delete
```

---

## ⏰ 자동화 설정

### Cron 설정 (일간 실행)

```bash
# crontab -e
# 매일 오전 9시에 PRODUCTION 모드 실행
0 9 * * * cd /home/ubuntu/ares7-ensemble && /usr/bin/python3 run_pead_buyback_ensemble_prod.py >> /tmp/ares8_cron.log 2>&1
```

**주의사항**:
- cron 환경에서는 `ENABLE_RD_MODE` 환경변수가 자동으로 비어있음 (PRODUCTION 모드)
- 절대 경로 사용 권장: `/usr/bin/python3`
- 로그 파일 경로 명시: `>> /tmp/ares8_cron.log 2>&1`

### Systemd Service 설정 (권장)

**서비스 파일 생성**: `/etc/systemd/system/ares8-ensemble.service`

```ini
[Unit]
Description=ARES8 PEAD Only Overlay Strategy
After=network.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/ares7-ensemble
Environment="ENABLE_RD_MODE=0"
ExecStart=/usr/bin/python3 run_pead_buyback_ensemble_prod.py
StandardOutput=append:/var/log/ares8-ensemble.log
StandardError=append:/var/log/ares8-ensemble-error.log

[Install]
WantedBy=multi-user.target
```

**서비스 활성화**:
```bash
sudo systemctl daemon-reload
sudo systemctl enable ares8-ensemble.service
sudo systemctl start ares8-ensemble.service
sudo systemctl status ares8-ensemble.service
```

**타이머 설정** (일간 실행): `/etc/systemd/system/ares8-ensemble.timer`

```ini
[Unit]
Description=ARES8 Daily Execution Timer

[Timer]
OnCalendar=daily
OnCalendar=09:00
Persistent=true

[Install]
WantedBy=timers.target
```

**타이머 활성화**:
```bash
sudo systemctl enable ares8-ensemble.timer
sudo systemctl start ares8-ensemble.timer
sudo systemctl list-timers
```

---

## 📞 지원 및 문의

### 문서
- **배포 가이드**: `EC2_DEPLOYMENT_RUNBOOK.md` (이 문서)
- **상세 문서**: `WRAPPER_SCRIPTS_README.md`
- **빠른 시작**: `ARES8_QUICK_START.md`

### 코드
- **PRODUCTION 스크립트**: `run_pead_buyback_ensemble_prod.py`
- **R&D 스크립트**: `run_buyback_v2_real.py`
- **Pure Tilt 엔진**: `research/pead/event_book.py`

### 긴급 연락
- **프로젝트**: ARES7/ARES8 Ensemble
- **담당**: Quant Research Team
- **EC2**: 3.35.141.47 (kimera1023.pem)

---

## 📝 변경 이력

| 날짜 | 버전 | 변경 내용 |
|------|------|-----------|
| 2025-12-01 | 1.0 | 초기 버전 작성 (EC2 배포 완료) |

---

**END OF RUNBOOK**
