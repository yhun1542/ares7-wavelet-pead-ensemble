# SEC-API를 통한 Guidance Revision 데이터 추출 가능성 분석

## 📋 8-K Form Items 구조

### **Item 2.02: Results of Operations and Financial Condition**

**목적**: 회사가 재무 실적 및 재무 상태에 대한 정보를 공개할 때 사용

**포함 내용**:
- Quarterly/Annual earnings announcements
- Press releases with financial results
- **Forward-looking statements (Guidance)** ⭐
- Revenue/EPS guidance
- Outlook statements

**제출 시점**:
- Earnings call 전후
- Press release 발표 시
- 실적 발표 시

**Exhibit 99.1**: 보통 earnings press release 첨부 (Guidance 포함 가능성 높음)

---

### **Item 7.01: Regulation FD Disclosure**

**목적**: Regulation Fair Disclosure에 따른 비공개 정보 공개

**포함 내용**:
- Investor presentations
- Conference call scripts
- **Guidance updates** ⭐
- Material non-public information

---

### **Item 8.01: Other Events**

**목적**: 기타 중요한 이벤트

**포함 내용**:
- Business updates
- **Guidance revisions** (때때로)
- Strategic announcements

---

## 🎯 SEC-API를 통한 Guidance 추출 전략

### **Step 1: 8-K Item 2.02 + Exhibit 99.1 검색**

```json
{
  "query": "formType:\"8-K\" AND items:\"2.02\"",
  "from": "0",
  "size": "100"
}
```

### **Step 2: Exhibit 99.1 (Press Release) 다운로드**

- 대부분의 earnings announcement에 Guidance 포함
- PDF 또는 HTML 형식

### **Step 3: NLP로 Guidance 추출**

**키워드 검색**:
- "guidance"
- "outlook"
- "expect"
- "forecast"
- "anticipate"
- "project"
- "estimate"

**패턴 매칭**:
```
"We expect revenue of $X to $Y million"
"EPS guidance of $A to $B"
"Full year 2025 revenue expected to be..."
```

### **Step 4: 구조화된 데이터로 변환**

```python
{
    'ticker': 'AAPL',
    'report_date': '2025-01-28',
    'fiscal_period': 'Q1 2025',
    'guidance_type': 'revenue',
    'guidance_low': 100.0,  # billion
    'guidance_high': 105.0,
    'guidance_midpoint': 102.5,
    'previous_guidance_midpoint': 98.0,
    'revision_pct': 4.6  # (102.5 - 98.0) / 98.0
}
```

---

## ✅ SEC-API 장점

1. **무료 API Key 사용 가능** (이미 보유)
2. **모든 8-K 파일 접근 가능** (1993년~현재)
3. **Exhibit 다운로드 지원**
4. **구조화된 메타데이터** (items, filedAt 등)

---

## ⚠️ 도전 과제

### 1. **비구조화된 텍스트 데이터**
- Guidance가 자유 형식 텍스트로 작성됨
- 회사마다 표현 방식 다름
- 예: "mid-single digit growth" vs "$100-110M"

### 2. **NLP 복잡도**
- 숫자 추출 (revenue, EPS)
- 단위 변환 (million, billion, per share)
- 조건부 표현 ("excluding one-time items")
- 정성적 표현 ("strong growth expected")

### 3. **Guidance 제공 여부 불확실**
- 모든 회사가 Guidance를 제공하지 않음
- 일부는 구두로만 제공 (transcript 필요)
- 일부는 Guidance를 철회하기도 함

### 4. **Revision 추적 복잡도**
- 이전 Guidance와 비교 필요
- 시계열 데이터 구축 필요
- 회계 기준 변경 고려 필요

---

## 🚀 실행 가능성 평가

### **난이도**: 중상 (7/10)

### **예상 소요 시간**: 2-3주
- Week 1: 8-K 검색 + Exhibit 다운로드 파이프라인
- Week 2: NLP 파서 구현 (regex + spaCy)
- Week 3: 데이터 검증 + 시계열 구축

### **성공 확률**: 60-70%
- 대형주 (S&P 100): 80% (Guidance 제공 비율 높음)
- 중소형주: 40-50% (Guidance 제공 비율 낮음)

---

## 💡 권장 접근법

### **Option A: 간단한 키워드 기반 (빠름)**

```python
# 1. 8-K Item 2.02 검색
# 2. Exhibit 99.1 다운로드
# 3. "guidance" 키워드 포함 여부만 확인
# 4. Guidance 발표 이벤트 테이블 생성
# 5. Forward return 분석 (PEAD 방식과 동일)
```

**장점**:
- 구현 빠름 (3-5일)
- Guidance 발표 "이벤트" 자체의 효과 측정 가능

**단점**:
- Revision 크기 정량화 불가
- 상향/하향 구분 어려움

---

### **Option B: 정교한 NLP 파서 (느림)**

```python
# 1. 8-K Item 2.02 검색
# 2. Exhibit 99.1 다운로드
# 3. spaCy + regex로 숫자 추출
# 4. Guidance 값 구조화
# 5. 이전 Guidance와 비교하여 Revision 계산
# 6. Revision 크기별 Forward return 분석
```

**장점**:
- Revision 크기 정량화 가능
- 상향/하향 구분 가능
- 더 정교한 알파 분석

**단점**:
- 구현 복잡 (2-3주)
- 파싱 오류 가능성

---

## 📊 비교: PEAD vs Guidance Revision

| 항목 | PEAD (EPS Surprise) | Guidance Revision |
|------|---------------------|-------------------|
| **데이터 소스** | SF1 (완료) | SEC-API (파싱 필요) |
| **구조화 정도** | 완전 구조화 | 비구조화 (NLP 필요) |
| **난이도** | 낮음 | 중상 |
| **소요 시간** | 완료 | 2-3주 |
| **커버리지** | 100개 종목 | 50-80개 종목 (추정) |
| **신뢰도** | 높음 | 중간 (파싱 오류) |
| **알파 크기** | 확인됨 (Val Sharpe 0.26) | 미확인 |

---

## 🎯 최종 권장사항

### **Phase 1: PEAD 결과로 최종 정리** (즉시)
- 이미 완료된 PEAD v1 분석 사용
- Guidance Revision은 향후 과제로 홀딩

### **Phase 2: Guidance Event 분석** (선택적, 1주)
- Option A (키워드 기반) 구현
- Guidance 발표 이벤트 자체의 효과 측정
- PEAD와 비교

### **Phase 3: Guidance Revision 정량화** (선택적, 2-3주)
- Option B (NLP 파서) 구현
- Revision 크기별 알파 분석
- I/B/E/S 데이터와 비교

---

## 🛠️ 즉시 실행 가능한 코드 (Option A)

```python
import requests
import re
from datetime import datetime

API_KEY = "c2c08a95c67793b5a8bbba1e51611ed466900124e70c0615badefea2c6d429f9"
BASE_URL = "https://api.sec-api.io"

def search_8k_item_202(ticker, start_date, end_date):
    """8-K Item 2.02 검색"""
    query = {
        "query": f'ticker:{ticker} AND formType:"8-K" AND items:"2.02" AND filedAt:[{start_date} TO {end_date}]',
        "from": "0",
        "size": "100",
        "sort": [{"filedAt": {"order": "desc"}}]
    }
    
    headers = {"Authorization": API_KEY}
    response = requests.post(f"{BASE_URL}/query", json=query, headers=headers)
    return response.json()

def download_exhibit_99(filing_url):
    """Exhibit 99.1 다운로드"""
    # SEC EDGAR URL에서 exhibit 추출
    # ...
    pass

def has_guidance_keyword(text):
    """Guidance 키워드 포함 여부 확인"""
    keywords = ['guidance', 'outlook', 'expect', 'forecast', 'anticipate', 'project']
    return any(kw in text.lower() for kw in keywords)

# 예시 실행
filings = search_8k_item_202('AAPL', '2020-01-01', '2025-12-01')
print(f"Found {len(filings.get('filings', []))} 8-K filings with Item 2.02")
```

---

**다음 단계를 어떻게 진행하시겠습니까?**
