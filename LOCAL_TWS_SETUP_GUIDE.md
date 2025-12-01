# 로컬 PC TWS + EC2 연동 가이드

## 📋 개요

로컬 PC에서 TWS(Trader Workstation)를 실행하고, SSH 터널링을 통해 EC2의 IBKR API 스크립트와 연결하는 방법입니다.

---

## 🔧 1단계: TWS 설치 (로컬 PC)

### Windows/Mac 다운로드

**Paper Trading (테스트용)**:
https://www.interactivebrokers.com/en/trading/tws-papertrading.php

**Live Trading (실전용)**:
https://www.interactivebrokers.com/en/trading/tws.php

### 설치
1. 다운로드한 설치 파일 실행
2. 기본 설정으로 설치 진행
3. 설치 완료 후 TWS 실행

---

## 🔐 2단계: TWS 로그인

### 계정 정보
- **Username**: jasonjun0612
- **Password**: Kimerajason1542!

### 로그인 절차
1. TWS 실행
2. Username/Password 입력
3. **2중인증** 승인 (핸드폰)
4. Trading Mode 선택:
   - **Paper Trading** (테스트용) - 권장
   - **Live Trading** (실전용)

---

## ⚙️ 3단계: API 설정 활성화

### TWS 설정

1. **File** → **Global Configuration** (또는 Edit → Global Configuration)

2. **API → Settings** 탭 선택

3. 다음 옵션 체크:
   - ✅ **Enable ActiveX and Socket Clients**
   - ✅ **Allow connections from localhost only** (체크 해제)
   - ✅ **Read-Only API** (선택 사항)
   - ✅ **Download open orders on connection**

4. **Socket Port** 확인:
   - Paper Trading: **7497**
   - Live Trading: **7496**

5. **Trusted IPs** 추가:
   ```
   127.0.0.1
   ```

6. **OK** 클릭하여 저장

7. **TWS 재시작** (설정 적용)

---

## 🌐 4단계: SSH 터널링 설정

### Windows (PowerShell 또는 CMD)

```powershell
ssh -i C:\path\to\kimera1023.pem -R 7497:localhost:7497 ubuntu@3.35.141.47
```

**설명**:
- `-R 7497:localhost:7497`: 로컬 PC의 포트 7497을 EC2의 포트 7497로 포워딩
- EC2에서 `localhost:7497`로 접속하면 로컬 PC의 TWS로 연결됨

### Mac/Linux (Terminal)

```bash
ssh -i ~/path/to/kimera1023.pem -R 7497:localhost:7497 ubuntu@3.35.141.47
```

### 연결 유지

SSH 터널링은 **터미널을 닫으면 끊어집니다**.
- 터미널을 계속 열어두거나
- `screen` 또는 `tmux` 사용
- 또는 `autossh` 사용 (자동 재연결)

---

## 🧪 5단계: EC2에서 IBKR API 테스트

### SSH 터널링 연결 후

```bash
# EC2에 접속 (새 터미널)
ssh -i kimera1023.pem ubuntu@3.35.141.47

# ARES7 venv 활성화
cd /home/ubuntu/ares7-ensemble
source /home/ubuntu/ARES7-v2-Turbo/venv/bin/activate

# IBKR API 연결 테스트
python3 ibkr_connect.py
```

### 예상 출력

```
================================================================================
IBKR API Connection Test
================================================================================
Connecting to IB Gateway at localhost:7497...
✅ Connected to IB Gateway
Account: DU1234567
Available Funds: $100,000.00
Net Liquidation: $100,000.00

Positions:
  AAPL: 10 shares @ $150.00
  MSFT: 20 shares @ $300.00

✅ Connection test successful!
```

---

## 🚀 6단계: 실전 주문 실행

### 주문 스크립트 실행

```bash
cd /home/ubuntu/ares7-ensemble

# 최종 weights 기반 주문 생성
python3 generate_orders_from_weights.py

# 주문 실행 (확인 필요)
python3 execute_orders_ibkr.py
```

---

## 📊 7단계: Dashboard에서 모니터링

### Dashboard 접속

```
http://3.35.141.47:5000
```

### 실시간 모니터링
- 포지션 현황
- PnL
- Leverage
- Kill Switch 제어

---

## 🔄 자동화 (선택 사항)

### Cron으로 매일 자동 실행

```bash
# Crontab 편집
crontab -e

# 매일 UTC 14:30 (미국 시장 오픈)
30 14 * * 1-5 /home/ubuntu/ares7-ensemble/run_full_pipeline.sh && /home/ubuntu/ares7-ensemble/execute_orders_ibkr.py >> /home/ubuntu/ares7-ensemble/logs/auto_trading.log 2>&1
```

---

## ⚠️ 주의사항

### 보안
- TWS API는 **로컬 네트워크**에서만 사용 권장
- SSH 터널링으로 안전하게 연결
- **Read-Only API** 모드 사용 권장 (처음에는)

### Paper Trading
- 실전 전에 **Paper Trading**으로 충분히 테스트
- 주문 로직 검증
- 리스크 관리 확인

### 연결 안정성
- SSH 터널링이 끊어지면 API 연결도 끊어짐
- `autossh` 또는 `screen` 사용 권장
- 연결 상태 모니터링

---

## 🐛 문제 해결

### TWS API 연결 실패

**증상**: `Connection refused` 에러

**해결**:
1. TWS API 설정 확인 (Enable ActiveX and Socket Clients)
2. Socket Port 확인 (7497 또는 7496)
3. TWS 재시작
4. 방화벽 확인

### SSH 터널링 끊김

**증상**: `Connection reset by peer`

**해결**:
```bash
# autossh 설치 (Mac/Linux)
brew install autossh  # Mac
sudo apt install autossh  # Linux

# autossh로 자동 재연결
autossh -M 0 -i kimera1023.pem -R 7497:localhost:7497 ubuntu@3.35.141.47
```

### 2중인증 문제

**증상**: 로그인 후 2중인증 대기

**해결**:
- 핸드폰에서 IBKR 앱 열기
- 알림 승인
- 또는 Security Code 입력

---

## 📞 지원

- **IBKR API 문서**: https://interactivebrokers.github.io/tws-api/
- **TWS 다운로드**: https://www.interactivebrokers.com/en/trading/tws.php
- **EC2 Dashboard**: http://3.35.141.47:5000

---

**모든 준비가 완료되었습니다!** 🚀

로컬 PC에서 TWS를 실행하고, SSH 터널링으로 EC2와 연결하면 즉시 사용 가능합니다.
