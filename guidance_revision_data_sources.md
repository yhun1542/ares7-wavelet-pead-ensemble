# Guidance Revision 데이터 소스 조사 결과

## 📊 주요 데이터 제공업체

### 1. **I/B/E/S (Institutional Brokers' Estimate System)** - LSEG (Refinitiv)
- **URL**: https://www.lseg.com/en/data-analytics/financial-data/company-data/ibes-estimates
- **제공 데이터**:
  - Analyst Estimates (EPS, Revenue 등)
  - **Company Guidance Data** ✅
  - Consensus Estimates
  - Estimate Revisions History
  - Comparable Actuals
- **커버리지**:
  - 23,000+ 기업
  - 90+ 국가
  - 19,000+ 애널리스트
  - 역사적 데이터: US 1976년부터, 국제 1987년부터
- **데이터 포맷**: CSV, HTML, JSON, PDF, Python, SQL, Text, User Interface, XML
- **업데이트**: Continuous, Daily
- **접근 방법**: API, Cloud, Deployed/Onsite Servers, Desktop, Digital Files, Excel, FTP
- **특징**: 
  - **Analyst Estimates + Company Guidance를 통합 제공** ⭐⭐⭐
  - 동일한 회계 기준으로 비교 가능
  - "I/B/E/S Mean Estimates at Time of Guidance" 제공
  - Guidance 발표 시점의 애널리스트 반응 추적 가능

---

### 2. **FactSet**
- **URL**: https://developer.factset.com/api-catalog/factset-estimates-api
- **제공 데이터**:
  - Analyst Estimates
  - Consensus Data
  - Estimate Revisions
  - Company Guidance (일부)
- **접근 방법**: API
- **특징**: 기관투자자 중심, 유료

---

### 3. **Bloomberg Terminal**
- **제공 데이터**:
  - Analyst Estimates
  - Company Guidance
  - Estimate Revisions History
  - Earnings Transcripts
- **특징**: 
  - 가장 포괄적인 데이터
  - 매우 고가 (연간 $20,000+)
  - Terminal 접근 필요

---

### 4. **Zacks Analyst Revisions** - Nasdaq Data Link
- **URL**: https://data.nasdaq.com/databases/ZREV
- **제공 데이터**:
  - Individual Analyst Estimates
  - Estimate Revisions
  - Ratings Revisions
- **커버리지**: 1,500+ US & Canadian 기업
- **특징**: 
  - 개별 애널리스트 레벨 데이터
  - Nasdaq Data Link를 통해 접근 가능 (유료)

---

### 5. **Financial Modeling Prep (FMP)**
- **URL**: https://site.financialmodelingprep.com/developer/docs/stable/financial-estimates
- **제공 데이터**:
  - Analyst Forecasts (Revenue, EPS)
  - Consensus Estimates
- **접근 방법**: API
- **특징**: 상대적으로 저렴, API 기반

---

### 6. **Benzinga Corporate Guidance API**
- **URL**: https://www.benzinga.com/apis/cloud-product/corporate-guidance/
- **제공 데이터**:
  - Earnings Projections
  - Revenue Targets
  - Operating Margin Estimates
- **접근 방법**: API
- **특징**: Real-time guidance updates

---

## 🎯 권장사항

### **최적 선택: I/B/E/S (LSEG/Refinitiv)**

**이유**:
1. **Company Guidance + Analyst Estimates 통합 제공** ⭐⭐⭐
2. 가장 긴 역사적 데이터 (1976년~)
3. 가장 넓은 커버리지 (23,000+ 기업)
4. "Mean Estimates at Time of Guidance" - Guidance 발표 시점의 애널리스트 반응 추적 가능
5. 학술 연구에서 표준으로 사용됨

**단점**:
- 매우 고가 (기관 라이선스 필요)
- 개인/소규모 팀 접근 어려움

---

## 💡 대안 (무료/저렴한 옵션)

### 1. **SEC EDGAR Filings 직접 파싱**
- **소스**: https://www.sec.gov/edgar
- **방법**: 
  - 8-K, 10-Q, 10-K 파일에서 Guidance 정보 추출
  - Earnings Call Transcripts 파싱
- **장점**: 무료
- **단점**: 
  - 구조화되지 않은 텍스트 데이터
  - NLP/파싱 복잡도 높음
  - 역사적 데이터 수집 시간 소요

### 2. **Financial Modeling Prep API**
- **가격**: $14-$99/month
- **제공**: Analyst Estimates (Guidance는 제한적)
- **적합**: 소규모 프로젝트

### 3. **Zacks via Nasdaq Data Link**
- **가격**: 유료 (구독 필요)
- **제공**: Analyst Revisions
- **적합**: US/Canadian 기업 중심

---

## 📋 현재 프로젝트 상황

### 사용 가능한 API Keys:
- ✅ SHARADAR (Nasdaq Data Link): `H6zH4Q2CDr9uTFk9koqJ`
- ✅ Alpha Vantage: `WA6OEWIF23A4LVGN`
- ✅ SEC-API: `c2c08a95c67793b5a8bbba1e51611ed466900124e70c0615badefea2c6d429f9`

### 확인된 사실:
1. **SF1 (SHARADAR)**: Guidance 데이터 없음 ❌
2. **Alpha Vantage**: EPS Surprise만 제공 (Guidance 없음) ❌
3. **SEC-API**: 8-K/10-Q 파일 접근 가능 (파싱 필요) ⚠️

---

## 🚀 실행 가능한 옵션

### Option 1: SEC-API로 Guidance 파싱 (무료)
- SEC-API Key 사용
- 8-K 파일에서 "guidance", "outlook", "forecast" 키워드 검색
- NLP로 EPS/Revenue guidance 추출
- **난이도**: 높음
- **시간**: 2-3주

### Option 2: Zacks Analyst Revisions (유료)
- Nasdaq Data Link 구독 필요
- 기존 SHARADAR API Key로 접근 가능 여부 확인
- **난이도**: 중간
- **비용**: 추가 구독료

### Option 3: I/B/E/S 접근 시도
- 대학/기관 라이선스 확인
- WRDS (Wharton Research Data Services) 통해 접근 가능 여부 확인
- **난이도**: 낮음 (접근만 되면)
- **비용**: 기관 라이선스 필요

### Option 4: PEAD 결과로 최종 정리 (현실적)
- 이미 완료된 PEAD v1 (EPS Surprise) 분석 사용
- Guidance Revision은 데이터 제약으로 홀딩
- **난이도**: 없음
- **비용**: 없음

---

## 📝 결론

**Guidance Revision 데이터는 주로 고가의 기관용 데이터 제공업체(I/B/E/S, Bloomberg, FactSet)에서만 제공됩니다.**

현재 프로젝트에서는:
1. **PEAD v1 (EPS Surprise) 결과를 최종 결과로 사용** (권장)
2. SEC-API로 Guidance 파싱 시도 (시간 여유 있을 경우)
3. Zacks 구독 여부 확인 (추가 비용 감당 가능 시)

**현실적 권장사항**: Option 4 (PEAD 결과로 최종 정리)
