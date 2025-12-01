# ARES8 PEAD Only - 완전 자동화 가이드

**작성일**: 2025-12-01  
**EC2**: 3.35.141.47  
**스크립트**: `run_pead_prod.sh`  
**상태**: ✅ **테스트 완료 및 즉시 사용 가능**

---

## 📋 목차

1. [자동화 스크립트 개요](#자동화-스크립트-개요)
2. [수동 실행 방법](#수동-실행-방법)
3. [로그 확인 방법](#로그-확인-방법)
4. [Cron 자동화 설정](#cron-자동화-설정)
5. [Systemd 타이머 설정](#systemd-타이머-설정)
6. [모니터링 및 알림](#모니터링-및-알림)
7. [문제 해결](#문제-해결)

---

## 🚀 자동화 스크립트 개요

### 파일 위치
```
/home/ubuntu/ares7-ensemble/run_pead_prod.sh
```

### 주요 기능

1. **R&D 모드 자동 OFF**
   - `ENABLE_RD_MODE` 자동 unset
   - 실수로 R&D 모드가 켜져있어도 강제로 OFF

2. **타임스탬프 기반 로그**
   - 로그 파일: `logs/pead_prod_YYYYMMDD_HHMMSS.log`
   - 실행 시간, 모드, Sharpe 자동 기록

3. **핵심 지표 자동 요약**
   - 모드 확인 (PROD/RD)
   - Alpha Buyback 확인 (0.0 예상)
   - Sharpe 확인 (0.504 예상)

4. **Exit Code 반환**
   - 성공: 0
   - 실패: 1 (에러 발생 시)

---

## 🖐️ 수동 실행 방법

### 1단계: EC2 접속

```bash
ssh -i kimera1023.pem ubuntu@3.35.141.47
```

### 2단계: 스크립트 실행

```bash
cd /home/ubuntu/ares7-ensemble
./run_pead_prod.sh
```

### 3단계: 실행 결과 확인

**예상 출력**:
```
================================================================================
[2025-12-01 15:44:17] ARES8 PEAD PROD RUN START
================================================================================

📍 Working Directory: /home/ubuntu/ares7-ensemble
📝 Log File: /home/ubuntu/ares7-ensemble/logs/pead_prod_20251201_154417.log
🐍 Python: /usr/bin/python3
🔒 MODE: PRODUCTION (ENABLE_RD_MODE unset)

✅ ENABLE_RD_MODE: (unset) - PRODUCTION MODE

================================================================================

[2025-12-01 15:44:17] Executing: python3 run_pead_buyback_ensemble_prod.py

================================================================================
[2025-12-01 15:44:22] ARES8 PEAD PROD RUN END (exit=0)
================================================================================

✅ Execution completed successfully

📁 Full log: /home/ubuntu/ares7-ensemble/logs/pead_prod_20251201_154417.log

================================================================================
📊 KEY METRICS SUMMARY
================================================================================

🔍 Mode Check:
[2025-12-01 15:44:18] ARES8 ENSEMBLE - PROD MODE

🔒 Alpha Buyback:
Alpha Buyback: 0.0 (LOCKED)
[2025-12-01 15:44:18] Alpha Buyback: 0.0

📈 Sharpe Ratios:
[2025-12-01 15:44:22] Base Test Sharpe: 0.451
[2025-12-01 15:44:22] Overlay Test Sharpe: 0.504
[2025-12-01 15:44:22] Incremental Sharpe: +0.053

================================================================================
```

---

## 📊 로그 확인 방법

### 최근 실행 로그 확인

```bash
cd /home/ubuntu/ares7-ensemble

# 가장 최근 로그 파일 찾기
ls -lt logs/pead_prod_*.log | head -1

# 최근 로그 내용 확인
LATEST_LOG=$(ls -t logs/pead_prod_*.log | head -1)
cat "$LATEST_LOG"
```

### 핵심 지표만 빠르게 확인

```bash
cd /home/ubuntu/ares7-ensemble

# 최근 로그에서 핵심 지표 추출
LATEST_LOG=$(ls -t logs/pead_prod_*.log | head -1)
grep -E "MODE|Alpha Buyback|Overlay Test Sharpe|Base Test Sharpe|Incremental Sharpe" "$LATEST_LOG"
```

**예상 출력**:
```
🔒 MODE: PRODUCTION (ENABLE_RD_MODE unset)
[2025-12-01 15:44:18] ARES8 ENSEMBLE - PROD MODE
Alpha Buyback: 0.0 (LOCKED)
[2025-12-01 15:44:18] Alpha Buyback: 0.0
[2025-12-01 15:44:22] Base Test Sharpe: 0.451
[2025-12-01 15:44:22] Overlay Test Sharpe: 0.504
[2025-12-01 15:44:22] Incremental Sharpe: +0.053
```

### 로그 파일 목록 확인

```bash
cd /home/ubuntu/ares7-ensemble

# 최근 10개 로그 파일
ls -lt logs/pead_prod_*.log | head -10

# 로그 파일 개수
ls logs/pead_prod_*.log | wc -l

# 로그 파일 총 크기
du -sh logs/
```

---

## ⏰ Cron 자동화 설정

### 1단계: Crontab 편집

```bash
crontab -e
```

### 2단계: Cron 작업 추가

#### 매일 오전 9시 실행 (권장)

```cron
# ARES8 PEAD Only - 매일 오전 9시 실행
0 9 * * * /home/ubuntu/ares7-ensemble/run_pead_prod.sh >> /home/ubuntu/ares7-ensemble/logs/cron_wrapper.log 2>&1
```

#### 매일 오전 9시 + 오후 3시 실행

```cron
# ARES8 PEAD Only - 매일 오전 9시, 오후 3시 실행
0 9,15 * * * /home/ubuntu/ares7-ensemble/run_pead_prod.sh >> /home/ubuntu/ares7-ensemble/logs/cron_wrapper.log 2>&1
```

#### 평일만 오전 9시 실행

```cron
# ARES8 PEAD Only - 평일 오전 9시 실행 (월~금)
0 9 * * 1-5 /home/ubuntu/ares7-ensemble/run_pead_prod.sh >> /home/ubuntu/ares7-ensemble/logs/cron_wrapper.log 2>&1
```

### 3단계: Cron 작업 확인

```bash
# Cron 작업 목록 확인
crontab -l

# Cron 로그 확인 (시스템 로그)
grep CRON /var/log/syslog | tail -20
```

### 4단계: Cron 실행 로그 확인

```bash
# Cron wrapper 로그 확인
tail -50 /home/ubuntu/ares7-ensemble/logs/cron_wrapper.log

# 실제 실행 로그 확인 (타임스탬프 기반)
ls -lt /home/ubuntu/ares7-ensemble/logs/pead_prod_*.log | head -5
```

---

## 🔧 Systemd 타이머 설정 (고급)

Cron보다 더 강력한 기능이 필요하면 Systemd 타이머를 사용하세요.

### 1단계: Service 파일 생성

```bash
sudo nano /etc/systemd/system/ares8-pead-prod.service
```

**내용**:
```ini
[Unit]
Description=ARES8 PEAD Only Production Strategy
After=network.target

[Service]
Type=oneshot
User=ubuntu
WorkingDirectory=/home/ubuntu/ares7-ensemble
ExecStart=/home/ubuntu/ares7-ensemble/run_pead_prod.sh
StandardOutput=append:/var/log/ares8-pead-prod.log
StandardError=append:/var/log/ares8-pead-prod-error.log

[Install]
WantedBy=multi-user.target
```

### 2단계: Timer 파일 생성

```bash
sudo nano /etc/systemd/system/ares8-pead-prod.timer
```

**내용**:
```ini
[Unit]
Description=ARES8 PEAD Only Daily Execution Timer

[Timer]
OnCalendar=daily
OnCalendar=09:00
Persistent=true

[Install]
WantedBy=timers.target
```

### 3단계: Systemd 활성화

```bash
# Daemon 리로드
sudo systemctl daemon-reload

# Service 활성화
sudo systemctl enable ares8-pead-prod.service

# Timer 활성화
sudo systemctl enable ares8-pead-prod.timer
sudo systemctl start ares8-pead-prod.timer

# Timer 상태 확인
sudo systemctl status ares8-pead-prod.timer
sudo systemctl list-timers
```

### 4단계: 수동 실행 테스트

```bash
# Service 수동 실행
sudo systemctl start ares8-pead-prod.service

# 실행 상태 확인
sudo systemctl status ares8-pead-prod.service

# 로그 확인
sudo journalctl -u ares8-pead-prod.service -n 50
```

---

## 📈 모니터링 및 알림

### 간단한 모니터링 스크립트

**파일**: `/home/ubuntu/ares7-ensemble/check_latest_run.sh`

```bash
#!/usr/bin/env bash
# 최근 실행 결과 요약

cd /home/ubuntu/ares7-ensemble

LATEST_LOG=$(ls -t logs/pead_prod_*.log 2>/dev/null | head -1)

if [ -z "$LATEST_LOG" ]; then
    echo "❌ No logs found"
    exit 1
fi

echo "📁 Latest log: $LATEST_LOG"
echo ""

# 실행 시간
echo "⏰ Execution time:"
grep "ARES8 PEAD PROD RUN" "$LATEST_LOG" | head -2 | tail -1

# 모드 확인
echo ""
echo "🔒 Mode:"
grep "MODE: PRODUCTION" "$LATEST_LOG" | head -1

# Alpha Buyback
echo ""
echo "🔒 Alpha Buyback:"
grep "Alpha Buyback: 0.0" "$LATEST_LOG" | head -1

# Sharpe
echo ""
echo "📈 Sharpe:"
grep -E "Overlay Test Sharpe|Incremental Sharpe" "$LATEST_LOG"

# Exit code
echo ""
echo "✅ Exit:"
grep "exit=" "$LATEST_LOG" | tail -1
```

**실행**:
```bash
chmod +x /home/ubuntu/ares7-ensemble/check_latest_run.sh
./check_latest_run.sh
```

### 이메일 알림 (선택사항)

Sharpe가 비정상이거나 실행 실패 시 이메일 알림을 받으려면:

```bash
# mailutils 설치
sudo apt-get install mailutils -y

# Cron에 알림 추가
0 9 * * * /home/ubuntu/ares7-ensemble/run_pead_prod.sh || echo "ARES8 execution failed" | mail -s "ARES8 Alert" your-email@example.com
```

---

## 🚨 문제 해결

### 문제 1: 스크립트 실행 권한 없음

**증상**:
```
bash: ./run_pead_prod.sh: Permission denied
```

**해결**:
```bash
chmod +x /home/ubuntu/ares7-ensemble/run_pead_prod.sh
```

### 문제 2: Python 경로 오류

**증상**:
```
python3: command not found
```

**해결**:
```bash
# Python 경로 확인
which python3

# 스크립트에서 절대 경로 사용
# run_pead_prod.sh 수정: python3 → /usr/bin/python3
```

### 문제 3: Cron에서 실행 안 됨

**증상**:
Cron 작업이 등록되었는데 실행 로그가 없음

**확인 순서**:

1. Cron 작업 확인:
   ```bash
   crontab -l
   ```

2. Cron 시스템 로그 확인:
   ```bash
   grep CRON /var/log/syslog | tail -20
   ```

3. 절대 경로 사용:
   ```cron
   # 상대 경로 (X)
   0 9 * * * cd /home/ubuntu/ares7-ensemble && ./run_pead_prod.sh
   
   # 절대 경로 (O)
   0 9 * * * /home/ubuntu/ares7-ensemble/run_pead_prod.sh
   ```

4. 환경변수 설정:
   ```cron
   # PATH 설정 추가
   PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
   0 9 * * * /home/ubuntu/ares7-ensemble/run_pead_prod.sh
   ```

### 문제 4: Sharpe 비정상 (< 0.4 또는 > 0.6)

**증상**:
```
Overlay Test Sharpe: 0.234  # 너무 낮음
```

**확인 순서**:

1. 모드 확인:
   ```bash
   grep "MODE" logs/pead_prod_*.log | tail -1
   # 예상: "PROD MODE"
   ```

2. Alpha Buyback 확인:
   ```bash
   grep "Alpha Buyback" logs/pead_prod_*.log | tail -1
   # 예상: "Alpha Buyback: 0.0"
   ```

3. 데이터 파일 확인:
   ```bash
   ls -lh data/*.csv
   wc -l data/*.csv
   ```

4. 전체 로그 확인:
   ```bash
   LATEST_LOG=$(ls -t logs/pead_prod_*.log | head -1)
   cat "$LATEST_LOG"
   ```

---

## 📝 체크리스트

### 초기 설정 (1회만)

- [ ] EC2 접속 확인
- [ ] 스크립트 파일 존재 확인: `ls -l run_pead_prod.sh`
- [ ] 실행 권한 확인: `chmod +x run_pead_prod.sh`
- [ ] 수동 실행 테스트: `./run_pead_prod.sh`
- [ ] Cron 또는 Systemd 설정

### 일상 운영

- [ ] 최근 로그 확인: `ls -lt logs/pead_prod_*.log | head -1`
- [ ] Sharpe 확인: 0.504 (±0.05)
- [ ] Alpha Buyback 확인: 0.0
- [ ] 모드 확인: PROD MODE

### 월간 유지보수

- [ ] 로그 파일 정리 (30일 이상 삭제)
- [ ] 디스크 공간 확인
- [ ] Cron 작업 확인
- [ ] 데이터 파일 무결성 확인

---

## 🎯 빠른 참조

### 한 줄 실행

```bash
# EC2 접속 후
cd /home/ubuntu/ares7-ensemble && ./run_pead_prod.sh
```

### 한 줄 확인

```bash
# 최근 실행 결과 요약
LATEST_LOG=$(ls -t /home/ubuntu/ares7-ensemble/logs/pead_prod_*.log | head -1) && grep -E "MODE|Alpha Buyback|Overlay Test Sharpe|exit=" "$LATEST_LOG"
```

### Cron 한 줄 설정

```bash
# Crontab에 추가 (매일 오전 9시)
(crontab -l 2>/dev/null; echo "0 9 * * * /home/ubuntu/ares7-ensemble/run_pead_prod.sh >> /home/ubuntu/ares7-ensemble/logs/cron_wrapper.log 2>&1") | crontab -
```

---

## 📞 지원

### 문서
- **자동화 가이드**: `AUTOMATION_GUIDE.md` (이 문서)
- **운영 Runbook**: `EC2_DEPLOYMENT_RUNBOOK.md`
- **배포 요약**: `EC2_DEPLOYMENT_SUMMARY.md`

### 스크립트
- **자동화 스크립트**: `run_pead_prod.sh`
- **Python 스크립트**: `run_pead_buyback_ensemble_prod.py`

### EC2
- **IP**: 3.35.141.47
- **User**: ubuntu
- **Key**: kimera1023.pem

---

**작성일**: 2025-12-01  
**버전**: 1.0  
**상태**: ✅ **테스트 완료 및 즉시 사용 가능**

**END OF AUTOMATION GUIDE**
