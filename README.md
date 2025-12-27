# Nongshim Competitor Compare

🍜 농심 제품과 경쟁사 제품을 실시간으로 비교하는 웹 애플리케이션

## 🎯 프로젝트 개요

사용자가 농심 제품명과 비교할 타사 제품명을 입력하면:
1. 외부 이커머스/가격비교 소스에서 별점/리뷰수/가격/상품정보를 수집
2. 수집한 리뷰 텍스트에서 특징/장점/단점을 LLM으로 추출하여 요약
3. 두 제품을 한 화면에서 비교 (표/카드/차트)

## 🚀 빠른 시작

### 로컬 실행 (Docker Compose)

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 설정

# 2. Docker Compose로 실행
docker-compose up --build

# 3. 접속
# - 백엔드 API: http://localhost:8000/docs
# - Streamlit UI: http://localhost:8501
```

### 개발 모드 실행

```bash
# 의존성 설치
make install

# 개발 모드 실행 (핫 리로드)
make run-dev
```

## 📁 프로젝트 구조

```
nongshim-competitor-compare/
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI 엔트리
│   │   ├── api.py           # 라우터
│   │   ├── config.py        # 환경 설정
│   │   ├── schemas.py       # Pydantic 스키마
│   │   ├── normalize.py     # 제품명 매칭/정규화
│   │   ├── aggregate.py     # 소스별 결과 통합
│   │   ├── llm_summarize.py # Titan 프롬프트/요약
│   │   ├── cache.py         # TTL 캐시/레이트리밋
│   │   └── sources/
│   │       ├── elevenst.py      # 11번가 API
│   │       ├── danawa.py        # 다나와 API
│   │       ├── naver_serpapi.py # SerpApi
│   │       └── scrape_fallback.py # 스크래핑 (OFF)
│   └── requirements.txt
├── streamlit_app/
│   ├── app.py               # 비교 UI
│   └── requirements.txt
├── tests/
│   ├── test_schemas.py
│   ├── test_normalize.py
│   ├── test_sources_mock.py
│   └── test_e2e_smoke.py
├── infra/
│   ├── docker/
│   │   ├── Dockerfile.backend
│   │   └── Dockerfile.streamlit
│   └── ecs/
│       └── deploy.sh
├── docker-compose.yml
├── Makefile
├── .env.example
└── README.md
```

## 🔧 설정

### 환경변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `ELEVENST_API_KEY` | 11번가 Open API 키 | - |
| `DANAWA_API_KEY` | 다나와 API 키 | - |
| `SERPAPI_API_KEY` | SerpApi 키 | - |
| `AWS_REGION` | AWS 리전 | ap-northeast-2 |
| `AWS_ACCESS_KEY_ID` | AWS 액세스 키 | - |
| `AWS_SECRET_ACCESS_KEY` | AWS 시크릿 키 | - |
| `CACHE_TTL_SECONDS` | 캐시 TTL (초) | 900 |
| `RATE_LIMIT_SECONDS` | 강제 새로고침 제한 (초) | 60 |
| `ENABLE_SCRAPING` | 스크래핑 활성화 | false |

## 📚 API 문서

### POST /compare

제품 비교 요청

**Request Body:**
```json
{
    "brand_a": "농심",
    "product_a": "신라면",
    "brand_b": "오뚜기",
    "product_b": "진라면 매운맛",
    "sources": ["11st", "danawa"],
    "force_refresh": false
}
```

**Response:**
```json
{
    "request_id": "uuid",
    "product_a": {
        "brand": "농심",
        "query": "신라면",
        "best_offer": {...},
        "key_features": ["특징1", "특징2"],
        "pros": ["장점1"],
        "cons": ["단점1"]
    },
    "product_b": {...},
    "comparison": {
        "rating_diff": 0.2,
        "price_diff_krw": -200,
        "review_count_diff": 100
    },
    "cached": false
}
```

### GET /health

헬스체크 엔드포인트

## 🧪 테스트

```bash
# 전체 테스트
make test

# 커버리지 포함
make test-cov
```

## 🚢 AWS 배포

### ECS Fargate 배포

```bash
# 1. 이미지 빌드 및 ECR 푸시
make push

# 2. ECS 배포
make deploy

# 3. 로그 확인
make logs
```

### 배포 URL

> 배포 완료 후 URL을 여기에 추가하세요:
> - API: `http://<ALB-DNS>:8000`
> - UI: `http://<ALB-DNS>:8501`

## ⚖️ 데이터 수집 정책

1. **공식 API 우선**: 11번가, 다나와 Open API 사용
2. **스크래핑은 기본 OFF**: `ENABLE_SCRAPING=true`로 활성화
3. **robots.txt/약관 준수**: 모든 스크래핑은 정책 준수
4. **레이트 리밋**: 
   - 캐시 TTL: 15분
   - 강제 새로고침: 1분에 1회
5. **User-Agent 명시**: 요청 시 식별 가능한 User-Agent 사용
6. **개인정보 수집 금지**

## 📄 라이선스

Private - 내부 사용 목적

## 🤝 기여

이슈 및 풀 리퀘스트는 GitHub에서 환영합니다.
