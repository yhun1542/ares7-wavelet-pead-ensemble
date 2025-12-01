# IB Key 자동 로그인 가이드

## 📋 개요

**IB Key**를 사용하면 IBKR 모바일 앱이 자동으로 로그인을 승인해주어, EC2에서 IB Gateway를 완전 자동으로 실행할 수 있습니다.

---

## 🔑 IB Key란?

- IBKR 모바일 앱 기반 인증 시스템
- 2중인증(2FA)을 자동으로 승인
- 로그인 시 핸드폰 승인 불필요
- **완전 자동화 가능**

---

## 📱 1단계: IBKR 모바일 앱 설치

### iOS
App Store에서 "IBKR Mobile" 검색 및 설치

### Android
Google Play에서 "IBKR Mobile" 검색 및 설치

---

## 🔐 2단계: IB Key 활성화

### IBKR 웹사이트에서 설정

1. **Client Portal 로그인**
   - https://www.interactivebrokers.com/sso/Login

2. **Account Management** 접속
   - 우측 상단 사용자 아이콘 클릭
   - "Manage Account" 선택

3. **Security** 섹션
   - "Secure Login System" 클릭
   - "IB Key" 선택

4. **IB Key 활성화**
   - "Enable IB Key" 클릭
   - 모바일 앱에서 QR 코드 스캔
   - 또는 Activation Code 입력

5. **확인**
   - 모바일 앱에서 "Activate" 클릭
   - IB Key 활성화 완료

---

## 📲 3단계: IBKR 모바일 앱 설정

### 로그인

1. IBKR Mobile 앱 실행
2. Username: **jasonjun0612**
3. Password: **Kimerajason1542!**
4. IB Key 승인

### IB Key 설정 확인

1. 앱 설정 → Security
2. "IB Key" 활성화 확인
3. "Auto-Approve Login" 옵션 확인 (선택 사항)

---

## 🖥️ 4단계: IBC 설정 업데이트 (EC2)

### IBC config.ini 수정

```bash
# EC2 접속
ssh -i kimera1023.pem ubuntu@3.35.141.47

# IBC 설정 파일 편집
sudo nano /opt/ibc/config.ini
```

### 설정 변경

```ini
# 기존 설정
IbLoginId=jasonjun0612
IbPassword=Kimerajason1542!
TradingMode=paper

# IB Key 관련 설정 추가
SecondFactorAuthenticationMethod=IB_KEY
# 또는
# SecondFactorAuthenticationMethod=IBKEY

# 자동 재시작 설정
ExitAfterSecondFactorAuthenticationTimeout=no
```

### 저장 및 종료
- `Ctrl+O` (저장)
- `Enter` (확인)
- `Ctrl+X` (종료)

---

## 🔄 5단계: IB Gateway 재시작

### 기존 프로세스 종료

```bash
sudo systemctl stop ibgateway 2>/dev/null
ps aux | grep -E 'ibgateway|GWClient' | grep -v grep | awk '{print $2}' | xargs sudo kill -9 2>/dev/null
```

### IB Gateway 재시작

```bash
cd /opt/ibc
sudo ./start-ibgateway.sh &
```

### 로그 모니터링

```bash
tail -f /var/log/ibgateway/gateway_direct.log
```

---

## 📱 6단계: 모바일 앱에서 승인

### 첫 로그인 시

1. IB Gateway가 로그인 시도
2. **IBKR 모바일 앱에 알림 도착**
3. 앱 열기 → "Approve" 클릭
4. 이후 자동 승인 (설정에 따라)

### Auto-Approve 설정 (선택 사항)

1. IBKR Mobile 앱 → Settings
2. Security → IB Key
3. "Auto-Approve Login" 활성화
4. 신뢰할 수 있는 디바이스에서만 사용 권장

---

## ✅ 7단계: 자동 로그인 확인

### API 포트 확인

```bash
# 포트 4001 리스닝 확인 (30초 대기)
sleep 30
netstat -tuln | grep 4001
```

**예상 출력**:
```
tcp        0      0 0.0.0.0:4001            0.0.0.0:*               LISTEN
```

### IBKR API 연결 테스트

```bash
cd /home/ubuntu/ares7-ensemble
source /home/ubuntu/ARES7-v2-Turbo/venv/bin/activate
python3 ibkr_connect.py
```

**예상 출력**:
```
✅ Connected to IB Gateway
Account: DU1234567
Available Funds: $100,000.00
```

---

## 🤖 8단계: 완전 자동화

### Systemd 서비스 생성

```bash
sudo nano /etc/systemd/system/ibgateway-auto.service
```

### 서비스 설정

```ini
[Unit]
Description=IB Gateway with Auto-Login
After=network.target

[Service]
Type=forking
User=root
WorkingDirectory=/opt/ibc
ExecStart=/opt/ibc/start-ibgateway.sh
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

### 서비스 활성화

```bash
sudo systemctl daemon-reload
sudo systemctl enable ibgateway-auto
sudo systemctl start ibgateway-auto
```

### 서비스 상태 확인

```bash
sudo systemctl status ibgateway-auto
```

---

## 🔍 문제 해결

### IB Key 승인 알림이 안 옴

**원인**: 모바일 앱이 백그라운드에 있거나 알림 비활성화

**해결**:
1. IBKR Mobile 앱 열기
2. 알림 권한 확인
3. 앱을 포그라운드로 유지

### 자동 로그인 실패

**원인**: IBC 설정 오류 또는 IB Key 미활성화

**해결**:
1. `/opt/ibc/config.ini` 확인
2. `SecondFactorAuthenticationMethod=IB_KEY` 설정 확인
3. IBKR 웹사이트에서 IB Key 활성화 확인

### API 포트 4001 안 열림

**원인**: 로그인 미완료 또는 API 설정 비활성화

**해결**:
1. 로그 확인: `tail -f /var/log/ibgateway/gateway_direct.log`
2. IB Gateway 재시작
3. 모바일 앱에서 수동 승인

---

## ⚠️ 주의사항

### 보안

- **Auto-Approve**는 신뢰할 수 있는 환경에서만 사용
- EC2 보안 그룹 설정 확인
- SSH 키 관리 철저히

### Paper Trading

- 실전 전에 **Paper Trading**으로 충분히 테스트
- 자동 로그인 동작 확인
- API 연결 안정성 확인

### 모바일 앱

- IBKR Mobile 앱을 항상 최신 버전으로 유지
- 알림 권한 활성화
- 배터리 최적화 예외 설정 (Android)

---

## 📊 자동화 완료 확인

### 체크리스트

- [ ] IB Key 활성화 (IBKR 웹사이트)
- [ ] IBKR Mobile 앱 로그인
- [ ] IBC 설정 업데이트 (`SecondFactorAuthenticationMethod=IB_KEY`)
- [ ] IB Gateway 재시작
- [ ] 모바일 앱에서 첫 로그인 승인
- [ ] API 포트 4001 열림 확인
- [ ] IBKR API 연결 테스트 성공
- [ ] Systemd 서비스 설정 (선택 사항)

---

## 🎯 최종 결과

**완전 자동화 달성!**

- ✅ EC2 재부팅 시 IB Gateway 자동 시작
- ✅ IB Key로 자동 로그인
- ✅ API 포트 4001 자동 활성화
- ✅ IBKR API 스크립트 즉시 사용 가능

---

## 📞 지원

- **IBKR IB Key 문서**: https://www.interactivebrokers.com/en/index.php?f=ibkey
- **IBC 문서**: https://github.com/IbcAlpha/IBC
- **Dashboard**: http://3.35.141.47:5000

---

**이제 완전 자동화된 트레이딩 시스템이 준비되었습니다!** 🚀
