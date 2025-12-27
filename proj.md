0) 프로젝트 개요
프로젝트명

nongshim-competitor-compare

목표

사용자가 “농심 제품명”과 “비교할 타사 제품명(또는 카테고리)”를 입력하면,

외부 이커머스/가격비교 소스에서 별점/리뷰수/가격/상품정보를 수집하고(가능하면 공식 API),

수집한 리뷰 텍스트/상품 스펙에서 특징/장점/단점을 추출해 요약하고(LLM 사용),

두 제품을 한 화면에서 비교(표/카드/차트)할 수 있게 한다.

“새로고침”을 누르면 그 시점 기준으로 재수집(단, 과도한 호출 방지 위해 캐시/TTL 적용)

비교 대상(고정 MVP 1쌍)

농심: 농심 신라면(봉지)

타사: 오뚜기 진라면(매운맛, 봉지)
(추후 사용자가 임의 제품도 비교 가능하게 확장)

1) 데이터 수집 정책(반드시 준수)
1-1. 소스 우선순위

1순위: 공식 Open API가 있는 소스

11번가 Open API(상품/정렬 옵션에 평가/리뷰수 등 활용 가능) 
SK Open API

다나와 Open API(상품코드 기반 정보 제공 가이드 존재) 
Danawa

2순위(옵션): 서드파티 SERP API

네이버 쇼핑 결과에서 rating/reviews를 제공하는 API(SerpApi 등) 
SerpApi

3순위(최후, 기본 OFF): HTML 스크래핑

반드시 robots.txt/약관 준수, 과도한 트래픽 금지

로그인 필요/캡차 우회/안티봇 회피/헤더 위조 등 차단 우회 코드는 절대 작성 금지

기본 구현은 OFF, 환경변수로 ENABLE했을 때만 동작하도록 한다.

1-2. “실시간”의 정의

사용자가 Compare 요청 시 즉시 수집하되,

같은 쿼리(제품 조합) 반복 요청은 TTL 캐시 15분을 적용한다.

캐시 우회(강제 새로고침)는 1분에 1회로 제한(Rate limit).

2) 아키텍처
2-1. 구성(권장)

Backend: FastAPI (REST)

Data fetch: requests/httpx (+ XML 파싱)

Cache: SQLite(간단) + in-memory LRU(TTL) 또는 Redis(선택)

LLM 요약: AWS Bedrock – amazon.titan-text-express-v1

Frontend: Streamlit (MVP)

Deploy: AWS ECS Fargate(컨테이너) 또는 AWS App Runner(가능하면)

“배포 후 URL 접속”으로 실제 확인 가능해야 함.

3) Repo 구조(필수)

다음 구조로 GitHub repo를 만든다(폴더/파일명 그대로):

backend/

app/main.py # FastAPI 엔트리

app/api.py # 라우터

app/config.py # env 로드

app/schemas.py # Pydantic 스키마

app/sources/

elevenst.py # 11번가 Open API 커넥터(가능하면)

danawa.py # 다나와 Open API 커넥터(가능하면)

naver_serpapi.py # (옵션) SerpApi 커넥터

scrape_fallback.py # (옵션, 기본 OFF) HTML 스크래핑 커넥터

app/normalize.py # 제품명 매칭/정규화/스코어링

app/aggregate.py # 소스별 결과 통합

app/llm_summarize.py # Titan 프롬프트/요약/장단점 추출(근거 기반)

app/cache.py # TTL 캐시/레이트리밋

app/utils.py

streamlit_app/

app.py # 비교 UI

infra/

docker/

Dockerfile.backend

Dockerfile.streamlit # 선택(한 컨테이너에 같이 넣어도 됨)

ecs/ # ECS 배포 스크립트 or Terraform/CDK

tests/

test_schemas.py

test_normalize.py

test_sources_mock.py # API 응답 fixture로 파싱 테스트

test_e2e_smoke.py

.env.example

docker-compose.yml # 로컬 원클릭 실행

Makefile # make run / make test / make deploy

README.md

4) 스키마(엄격)
4-1. CompareRequest

brand_a: Literal["농심"] (MVP 고정)

product_a: str (예: “신라면”)

brand_b: str (예: “오뚜기”)

product_b: str (예: “진라면 매운맛”)

sources: List[Literal["11st","danawa","naver_serpapi","scrape"]] (기본 ["11st","danawa"])

force_refresh: bool (기본 False)

4-2. Offer(소스별 상품 1개 결과)

source: str

title: str

url: str

price_krw: Optional[int]

rating: Optional[float] # 0~5 스케일로 정규화

review_count: Optional[int]

image_url: Optional[str]

fetched_at: str (ISO datetime)

4-3. ProductSummary(제품 단위 통합)

brand: str

query: str

best_offer: Offer # 대표 1개(스코어링으로 선택)

offers: List[Offer] # 소스별 후보

key_features: List[str] # 특징(근거 기반)

pros: List[str] # 장점(근거 기반)

cons: List[str] # 단점(근거 기반)

sentiment: {positive_pct, negative_pct, neutral_pct} # 가능하면(리뷰 텍스트 있을 때)

evidence: List[str] # “근거 문장/요약” (리뷰 텍스트/스펙에서 발췌한 짧은 문장)

4-4. CompareResponse

request_id: str

product_a: ProductSummary

product_b: ProductSummary

comparison: {
rating_diff: Optional[float],
price_diff_krw: Optional[int],
review_count_diff: Optional[int]
}

warnings: List[str]

cached: bool

5) 제품명 매칭/정규화(핵심)

사용자가 입력한 “신라면”이 소스에서는 “농심 신라면 120g 5개”처럼 나올 수 있다.

normalize.py에서:

한글/공백/괄호/용량/개수 제거 규칙

브랜드 키워드 포함 여부 가중치

문자열 유사도(예: rapidfuzz)로 top K 후보 선택

“대표 상품(best_offer)”는 score로 결정하되, 불확실하면 warnings에 후보를 남긴다.

6) LLM(Titan) 요약/장단점 추출(근거 기반 강제)

llm_summarize.py에서 Titan은 다음만 수행:

inputs: (a) 대표 상품 title, (b) 스펙/옵션 정보(가능하면), (c) 리뷰 텍스트(가능하면 일부), (d) rating/review_count

outputs: key_features/pros/cons/evidence 를 JSON으로만 출력

프롬프트 강제사항

“제공된 데이터(리뷰/스펙) 기반으로만” 작성

근거(evidence) 없이 단정 금지

리뷰 텍스트가 없으면 “리뷰 텍스트 부족”을 명시하고, features/pros/cons를 최소화

과장 광고 문구 금지

한국어로 간결하게(항목당 3~5개)

7) API 설계
7-1. 엔드포인트

POST /compare

body: CompareRequest

returns: CompareResponse

GET /health

7-2. 동작

입력 받기 → 소스 커넥터 병렬 호출 → 후보 offers 수집

normalize로 대표 상품 선정

가능한 경우 리뷰 텍스트 일부 수집(없으면 skip)

Titan 요약 생성(JSON-only)

비교값 계산

TTL 캐시 저장 후 반환

8) Streamlit UI(MVP)

좌측: 입력 폼

product_a 기본값: “신라면”

product_b 기본값: “진라면 매운맛”

sources 체크박스(기본 11st+danawa)

“강제 새로고침” 버튼(레이트 제한)

우측: 결과 영역

두 제품 카드(대표 이미지/가격/별점/리뷰수)

별점/가격/리뷰수 비교표

key_features/pros/cons 섹션

warnings 표시

“마지막 수집 시각” 표시

9) 테스트(필수)

소스 파서 테스트: fixture(XML/JSON)로 rating/price/review_count 파싱 검증

normalize 점수 로직 테스트

LLM 결과는 모킹하여 JSON-only/스키마 준수 검증

E2E smoke: /compare 호출 시 CompareResponse 스키마 만족

10) 로컬 실행 & 배포(반드시 “확인 가능한 URL”)
10-1. 로컬 원클릭

docker-compose up 으로

backend(8000)

streamlit(8501)

.env.example 제공(API 키 자리)

10-2. AWS 배포(필수)

infra에 배포 자동화 포함:

ECR에 이미지 push

ECS Fargate 서비스 생성(또는 App Runner)

보안그룹/ALB(필요 시)

배포 완료 후 접속 URL을 README에 명시

Makefile에:

make deploy (ap-southeast-2 기준)

make logs

11) 약관/안전(README에 명시)

공식 API 우선, 스크래핑 fallback은 기본 OFF

robots/약관 준수

호출 제한/캐시/레이트리밋 포함

사이트 요청 시 User-Agent 명시, 백오프 적용

개인 정보 수집 금지

12) 시작 순서(작업 순서 지시)

schemas.py 정의

sources 커넥터(11st/danawa) 구현 + fixture 기반 테스트

normalize → aggregate

llm_summarize(Titan JSON-only)

/compare API 완성

Streamlit UI 연결

docker-compose 로컬 동작 확인

AWS 배포 자동화(ecs/app runner)

README 정리(스크린샷/사용법/URL)