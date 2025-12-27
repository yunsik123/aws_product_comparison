# 농심 제품 비교 프로젝트 (Nongshim Competitor Compare)

## 📋 프로젝트 개요

농심 제품과 타사 제품을 실시간으로 비교하는 웹 애플리케이션

### 목표
- 외부 이커머스/가격비교 소스에서 별점/리뷰수/가격/상품정보 수집
- LLM으로 특징/장점/단점 추출 및 요약
- 두 제품을 한 화면에서 비교 (표/카드/차트)

### 비교 대상 (MVP)
- **농심**: 신라면 (봉지)
- **타사**: 오뚜기 진라면 (매운맛, 봉지)

---

## 🚀 배포 정보

### AWS Lambda API (서버리스)
- **API 엔드포인트**: https://2u1c4z6ehf.execute-api.ap-northeast-2.amazonaws.com
- **API 문서**: https://2u1c4z6ehf.execute-api.ap-northeast-2.amazonaws.com/docs
- **헬스 체크**: https://2u1c4z6ehf.execute-api.ap-northeast-2.amazonaws.com/health

### GitHub 레포지토리
- **URL**: https://github.com/yunsik123/aws_product_comparison

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
│   │   ├── aggregate.py      # 소스별 결과 통합
│   │   ├── cache.py          # TTL 캐시/레이트리밋
│   │   ├── llm_summarize.py  # AWS Bedrock Titan 연동
│   │   └── sources/
│   │       ├── elevenst.py       # 11번가 API
│   │       ├── danawa.py         # 다나와 웹스크래핑 (API 키 불필요)
│   │       ├── naver_serpapi.py  # SerpApi (옵션)
│   │       └── scrape_fallback.py
│   ├── lambda_handler.py     # Lambda 핸들러 (Mangum)
│   └── requirements.txt
├── streamlit_app/
│   └── app.py                # Streamlit UI
├── tests/
│   ├── test_schemas.py
│   ├── test_normalize.py
│   ├── test_sources_mock.py
│   └── test_e2e_smoke.py
├── deploy_lambda.ps1         # Lambda 배포 스크립트
├── docker-compose.yml        # 로컬 Docker 실행
├── Makefile
├── .env.example
├── .gitignore                # 민감 정보 제외
└── README.md
```

---

## 🔧 실행 방법

### 1. 로컬 실행 (개발)

```powershell
# 터미널 1 - 백엔드
cd backend
$env:PYTHONPATH=".."
uvicorn app.main:app --reload --port 8000

# 터미널 2 - Streamlit
cd streamlit_app
$env:BACKEND_URL="http://localhost:8000"
streamlit run app.py
```

### 2. 간편 실행 (PowerShell 스크립트)
```powershell
.\start.ps1
# Backend: http://localhost:8000/docs
# Streamlit: http://localhost:8501
```

### 3. Lambda 재배포
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
| Matching | rapidfuzz (문자열 유사도) |
| LLM | AWS Bedrock Titan (옵션) |
| Cache | In-memory LRU + SQLite |
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

### 테스트 결과
```
다나와 스크래핑 테스트:
- 농심신라면120g: 630원 ✓
- 농심신라면컵 65g: 800원 ✓
```

---

## 📌 참고사항

### 데이터 수집 정책
- **다나와 웹스크래핑**: API 키 불필요, 기본 활성화
- **11번가/SerpApi**: API 키 필요 (옵션)
- **캐시 TTL**: 15분
- **강제 새로고침 제한**: 1분에 1회

### 제한사항
- Streamlit UI는 로컬에서만 실행 (Lambda는 API만 배포)
- LLM 요약은 AWS Bedrock 설정 필요

---

## 🔗 링크

- **API 문서**: https://2u1c4z6ehf.execute-api.ap-northeast-2.amazonaws.com/docs
- **GitHub**: https://github.com/yunsik123/aws_product_comparison