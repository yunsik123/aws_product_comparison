# CLAUDE.md - 프로젝트 컨텍스트

## 프로젝트 개요

농심 라면 제품과 타사 제품(오뚜기, 삼양, 팔도)을 실시간으로 비교하는 웹 애플리케이션.
다나와 웹스크래핑으로 가격/평점/리뷰 데이터를 수집하고, AWS Lambda + DynamoDB로 서비스.

## 아키텍처

```
[로컬 PC] --다나와 스크래핑--> [DynamoDB] (가격 + 평점 + 리뷰 100개)
                                  |
[웹 브라우저] --> [S3 정적 웹] --> [API Gateway] --> [Lambda] --> [DynamoDB 읽기]
```

## 주요 명령어

```powershell
# 로컬 스크래퍼 실행 (가격 + 리뷰 100개 수집)
python local_scraper.py

# 리뷰 개수 지정
python local_scraper.py --reviews 50

# 리뷰 없이 빠르게 수집
python local_scraper.py --no-reviews

# 특정 제품만 수집
python local_scraper.py --query "신라면" --brand "농심"

# 저장된 데이터 확인
python local_scraper.py --list

# Lambda 배포
.\deploy_lambda.ps1

# 프론트엔드 S3 업로드
aws s3 cp frontend/index.html s3://nongshim-compare-web/index.html --content-type "text/html; charset=utf-8"
```

## 배포 URL

- **웹사이트**: http://nongshim-compare-web.s3-website.ap-northeast-2.amazonaws.com
- **API**: https://2u1c4z6ehf.execute-api.ap-northeast-2.amazonaws.com
- **API Docs**: https://2u1c4z6ehf.execute-api.ap-northeast-2.amazonaws.com/docs

## 지원 제품 목록

| 브랜드 | 제품 |
|--------|------|
| 농심 | 신라면, 신라면 컵, 짜파게티, 너구리, 안성탕면, 육개장 |
| 오뚜기 | 진라면, 진라면 매운맛, 참깨라면, 진짜장, 열라면, 스낵면 |
| 삼양 | 삼양라면, 불닭볶음면, 짜짜로니, 나가사키짬뽕, 맛있는라면 |
| 팔도 | 팔도비빔면, 왕뚜껑, 틈새라면, 꼬꼬면, 일품해물라면 |

## 리뷰 수집 기능

### 수집 데이터
- **평점**: 5점 만점 평균 평점
- **리뷰 수**: 전체 리뷰 개수
- **리뷰 텍스트**: 최신 리뷰 100개 (설정 가능)
  - 텍스트, 평점, 쇼핑몰명, 날짜, 포토리뷰 여부

### 기술 구현
- 다나와 AJAX API 직접 호출 (`companyProductReview.ajax.php`)
- **Selenium 불필요** - httpx 비동기 HTTP 클라이언트 사용
- 페이지네이션으로 여러 페이지 수집

### DynamoDB 저장 구조
```json
{
  "pk": "PRODUCT#농심",
  "sk": "QUERY#신라면",
  "best_rating": 4.7,
  "best_review_count": 61769,
  "reviews": [
    {"text": "맛있어요", "rating": 5.0, "mall": "쿠팡", "date": "2024.12.28", "has_photo": false},
    ...
  ],
  "reviews_count": 100
}
```

## 주요 파일

| 파일 | 설명 |
|------|------|
| `local_scraper.py` | 로컬에서 다나와 스크래핑 → DynamoDB 저장 |
| `backend/app/sources/danawa.py` | 다나와 스크래핑 로직 |
| `backend/app/llm_summarize.py` | 제품 분석 (제품 DB + LLM) |
| `backend/app/aggregate.py` | DynamoDB 연동, 데이터 통합 |
| `frontend/index.html` | 웹 프론트엔드 |
| `deploy_lambda.ps1` | Lambda 배포 스크립트 |

## 작업 이력

### 2025-12-29 리뷰 수집 기능 추가
- 다나와 AJAX API로 리뷰 텍스트 수집 (Selenium 제거)
- 제품당 최신 리뷰 100개 저장
- 평점/리뷰수 정확한 데이터 수집
- local_scraper.py 전면 개선

### 2025-12-29 제품 확장 및 스크래핑 개선
- 브랜드별 제품 22개 지원 (농심/오뚜기/삼양/팔도)
- 다나와 스크래핑 셀렉터 개선 (다중 셀렉터 시도)
- 프론트엔드 동적 제품 선택 구현
- LLM 대체용 제품 특성 DB 추가

### 2025-12-28 DynamoDB 아키텍처
- 로컬 스크래퍼 + DynamoDB 구조로 AWS IP 차단 우회
- Lambda는 DynamoDB 읽기 전용

### 2025-12-28 웹 프론트엔드
- S3 정적 웹사이트 호스팅
- Bootstrap 5 기반 UI

### 2025-12-27 초기 구현
- FastAPI 백엔드
- 다나와 웹스크래핑
- AWS Lambda 배포
