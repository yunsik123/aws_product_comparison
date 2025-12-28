# 농심 제품 비교 프로젝트 (Nongshim Competitor Compare)

## 📋 프로젝트 개요

농심 제품과 타사 제품을 실시간으로 비교하는 웹 애플리케이션

### 목표
- 다나와에서 실시간 웹스크래핑으로 별점/리뷰수/가격/상품정보 수집
- LLM으로 특징/장점/단점 추출 및 요약
- 두 제품을 한 화면에서 비교 (표/카드/차트)

### 비교 대상 (MVP)
- **농심**: 신라면 (봉지)
- **타사**: 오뚜기 진라면 (매운맛, 봉지)

---

## 🚀 배포 정보

### 웹사이트 (S3 정적 호스팅)
- **웹사이트 URL**: http://nongshim-compare-web.s3-website.ap-northeast-2.amazonaws.com

### AWS Lambda API (서버리스)
- **API 엔드포인트**: https://2u1c4z6ehf.execute-api.ap-northeast-2.amazonaws.com
- **API 문서**: https://2u1c4z6ehf.execute-api.ap-northeast-2.amazonaws.com/docs
- **헬스 체크**: https://2u1c4z6ehf.execute-api.ap-northeast-2.amazonaws.com/health

### GitHub 레포지토리
- **URL**: https://github.com/yunsik123/aws_product_comparison

---

## 🏗️ 아키텍처

```
[로컬 PC] --스크래핑--> [다나와]
    |
    v (local_scraper.py)
[DynamoDB] <--읽기-- [Lambda API] <--요청-- [사용자]
```

- **로컬 스크래퍼**: 로컬 PC에서 다나와 스크래핑 (AWS IP 차단 우회)
- **DynamoDB**: 스크래핑된 데이터 저장소 (TTL 24시간)
- **Lambda API**: DynamoDB에서 데이터 읽어서 제공

---

## 📁 프로젝트 구조

```
aws_product_comparison/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI 엔트리
│   │   ├── api.py            # 라우터 (/compare, /health)
│   │   ├── config.py         # 환경변수 설정
│   │   ├── schemas.py        # Pydantic 스키마
│   │   ├── normalize.py      # 제품명 매칭/정규화 (rapidfuzz)
│   │   ├── aggregate.py      # 소스별 결과 통합 + DynamoDB 연동
│   │   ├── dynamodb_client.py # DynamoDB 클라이언트
│   │   ├── cache.py          # TTL 캐시/레이트리밋
│   │   ├── llm_summarize.py  # AWS Bedrock Titan 연동
│   │   └── sources/
│   │       └── danawa.py     # 다나와 웹스크래핑 (API 키 불필요)
│   ├── lambda_handler.py     # Lambda 핸들러 (Mangum)
│   └── requirements.txt
├── streamlit_app/
│   └── app.py                # Streamlit UI
├── local_scraper.py          # 로컬 스크래퍼 (DynamoDB 저장)
├── setup_dynamodb.ps1        # DynamoDB 테이블 생성
├── deploy_lambda.ps1         # Lambda 배포 스크립트
├── tests/
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

---

## 🔧 실행 방법

### 1. 초기 설정 (처음 한 번만)
```powershell
# DynamoDB 테이블 생성
.\setup_dynamodb.ps1
```

### 2. 로컬 스크래퍼 실행 (데이터 수집)
```powershell
# 기본 상품 스크래핑 (농심/오뚜기/삼양/팔도)
python local_scraper.py

# 특정 상품 검색
python local_scraper.py --query "신라면" --brand "농심"

# 30분마다 자동 갱신
python local_scraper.py --loop 30

# 저장된 데이터 확인
python local_scraper.py --list
```

### 3. 로컬 백엔드/Streamlit 실행
```powershell
.\start.ps1
# Backend: http://localhost:8000/docs
# Streamlit: http://localhost:8501
```

### 4. Lambda 배포
```powershell
.\deploy_lambda.ps1
```

---

## 📊 API 스키마

### POST /compare
```json
{
    "brand_a": "농심",
    "product_a": "신라면",
    "brand_b": "오뚜기",
    "product_b": "진라면 매운맛",
    "sources": ["danawa"],
    "force_refresh": false
}
```

### Response
```json
{
    "request_id": "uuid",
    "product_a": {
        "brand": "농심",
        "query": "신라면",
        "best_offer": {
            "source": "danawa",
            "title": "농심 신라면 120g",
            "price_krw": 630,
            "rating": 4.5,
            "review_count": 1000
        },
        "key_features": ["매운맛", "봉지면"],
        "pros": ["저렴함", "맛있음"],
        "cons": ["나트륨 높음"]
    },
    "product_b": {...},
    "comparison": {
        "rating_diff": 0.2,
        "price_diff_krw": -100,
        "review_count_diff": 500
    },
    "cached": false
}
```

---

## ⚙️ 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | FastAPI, Pydantic, httpx |
| Data | BeautifulSoup (다나와 스크래핑) |
| Database | AWS DynamoDB (서버리스) |
| Matching | rapidfuzz (문자열 유사도) |
| LLM | AWS Bedrock Titan (옵션) |
| Cache | DynamoDB + In-memory LRU |
| Deploy | AWS Lambda + API Gateway |
| Frontend | Streamlit |

---

## 🔐 보안

### .gitignore에서 제외되는 민감 파일
- `.env`, `.env.local` - API 키
- `.aws/` - AWS 자격증명
- `**/secrets.py`, `**/api_keys.py` - 비밀 키 파일
- `*.zip` - 배포 패키지

---

## 📝 구현 히스토리

### 2024-12-27 구현 완료
1. ✅ 프로젝트 구조 생성 (22개 파일)
2. ✅ Pydantic 스키마 정의
3. ✅ 데이터 소스 커넥터 (다나와 웹스크래핑)
4. ✅ 제품명 정규화/매칭 로직
5. ✅ TTL 캐시 + 레이트 리밋
6. ✅ FastAPI API 엔드포인트
7. ✅ Streamlit UI
8. ✅ AWS Lambda 서버리스 배포
9. ✅ GitHub 푸시

### 2025-12-28 리팩토링
1. ✅ 다나와 전용으로 코드 간소화 (네이버/11번가 소스 제거)
2. ✅ config.py 불필요한 API 키 설정 제거
3. ✅ Lambda 배포 스크립트 개선 (Linux x86_64 호환 빌드)
4. ✅ AWS Lambda 재배포 완료

### 2025-12-28 DynamoDB 아키텍처 추가
1. ✅ DynamoDB 테이블 생성 스크립트 (setup_dynamodb.ps1)
2. ✅ 로컬 스크래퍼 구현 (local_scraper.py)
3. ✅ Lambda에서 DynamoDB 읽기 기능 추가
4. ✅ IAM 역할에 DynamoDB 권한 추가
5. ✅ 테스트 완료 - API가 DynamoDB 캐시에서 데이터 제공

### 2025-12-28 웹 프론트엔드 배포
1. ✅ HTML/CSS/JS 프론트엔드 작성 (Bootstrap 5)
2. ✅ S3 정적 웹사이트 호스팅 설정
3. ✅ 웹사이트 배포 완료
4. ✅ http://nongshim-compare-web.s3-website.ap-northeast-2.amazonaws.com

### 2025-12-29 제품 확장 및 개선
1. ✅ 브랜드별 제품 지원 확대 (6개 → 20개+)
   - 농심: 신라면, 짜파게티, 너구리, 안성탕면, 육개장
   - 오뚜기: 진라면, 참깨라면, 진짜장, 열라면, 스낵면
   - 삼양: 삼양라면, 불닭볶음면, 짜짜로니, 나가사키짬뽕
   - 팔도: 팔도비빔면, 왕뚜껑, 틈새라면, 꼬꼬면, 일품해물라면
2. ✅ 프론트엔드 동적 제품 선택 (브랜드별 제품 목록 자동 업데이트)
3. ✅ 다나와 스크래핑 개선 (다중 CSS 셀렉터 시도)
4. ✅ LLM 대체용 제품 특성 데이터베이스 추가 (`llm_summarize.py`)
5. ✅ brand_a 고정값 제거 (모든 브랜드 선택 가능)

### 테스트 결과
```
API 테스트 (2025-12-28):
- 신라면: 630원 ✓
- 진라면: 450원 ✓
- 가격 차이: 180원 (신라면 > 진라면) ✓
```

---

## 📌 참고사항

### 데이터 수집 정책
- **로컬 스크래퍼**: 로컬 PC에서 다나와 스크래핑 → DynamoDB 저장
- **DynamoDB TTL**: 24시간 (자동 만료)
- **Lambda**: DynamoDB에서 캐시된 데이터 읽기만

### 제한사항
- Streamlit UI는 로컬에서만 실행 (Lambda는 API만 배포)
- LLM 요약은 AWS Bedrock 설정 필요
- 주기적으로 `python local_scraper.py`를 실행해서 데이터 갱신 필요

### 평점/리뷰 수 수집 제한

**현재 상태**: 다나와에서 평점/리뷰 수 수집 불가

**원인 분석**:
1. 검색 결과 페이지에 평점/리뷰 정보 미포함
2. 상세 페이지의 평점/리뷰는 JavaScript 동적 로딩
3. AJAX API 엔드포인트 접근 제한 (404 또는 HTML만 반환)

**대안 (현재 구현)**:
- `llm_summarize.py`에 라면 제품별 특성 DB 구축 (20개+ 제품)
- 가격/제품 정보 기반으로 기본 장단점 분석 제공

**해결 방법 (미구현)**:
- Selenium/Playwright 브라우저 자동화 (Lambda에서 복잡, 비용 증가)
- 다나와 공식 API 계약 (비용 발생)

---

## 🔗 링크

- **API 문서**: https://2u1c4z6ehf.execute-api.ap-northeast-2.amazonaws.com/docs
- **GitHub**: https://github.com/yunsik123/aws_product_comparison