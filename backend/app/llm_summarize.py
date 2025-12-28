"""LLM summarization using AWS Bedrock Titan."""
import json
from typing import Dict, List, Optional
import boto3
from botocore.exceptions import ClientError

from .config import get_settings
from .schemas import ProductSummary, Offer


def get_bedrock_client():
    """Get AWS Bedrock runtime client."""
    settings = get_settings()
    
    kwargs = {
        "service_name": "bedrock-runtime",
        "region_name": settings.aws_region,
    }
    
    if settings.aws_access_key_id and settings.aws_secret_access_key:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    
    return boto3.client(**kwargs)


def build_summarize_prompt(
    offer: Offer,
    additional_info: Optional[str] = None,
    reviews: Optional[List[str]] = None
) -> str:
    """Build the prompt for Titan to generate product summary.
    
    The prompt enforces evidence-based responses only.
    """
    # Prepare product info
    product_info = f"""
제품명: {offer.title}
가격: {offer.price_krw:,}원 if offer.price_krw else "정보 없음"
별점: {offer.rating}/5.0 if offer.rating else "정보 없음"
리뷰 수: {offer.review_count}개 if offer.review_count else "정보 없음"
"""
    
    if additional_info:
        product_info += f"\n추가 정보: {additional_info}"
    
    # Add reviews if available
    reviews_section = ""
    if reviews and len(reviews) > 0:
        reviews_text = "\n".join([f"- {r}" for r in reviews[:10]])  # Max 10 reviews
        reviews_section = f"\n\n고객 리뷰:\n{reviews_text}"
    else:
        reviews_section = "\n\n(리뷰 텍스트 정보 없음)"
    
    prompt = f"""당신은 제품 분석 전문가입니다. 아래 제공된 데이터만을 기반으로 제품의 특징, 장점, 단점을 분석하세요.

중요 규칙:
1. 제공된 데이터(제품 정보, 리뷰)에서 직접 추출할 수 있는 내용만 작성하세요.
2. 근거 없이 추측하거나 일반적인 내용을 작성하지 마세요.
3. 리뷰 텍스트가 없으면 "리뷰 데이터 부족으로 상세 분석 불가"라고 명시하세요.
4. 과장된 광고 문구를 사용하지 마세요.
5. 각 항목은 3~5개로 제한하세요.
6. 한국어로 간결하게 작성하세요.

{product_info}
{reviews_section}

아래 JSON 형식으로만 응답하세요 (다른 텍스트 없이):
{{
    "key_features": ["특징1", "특징2", ...],
    "pros": ["장점1", "장점2", ...],
    "cons": ["단점1", "단점2", ...],
    "evidence": ["근거가 된 리뷰/정보 발췌1", "근거2", ...]
}}

리뷰 데이터가 부족한 경우:
{{
    "key_features": ["리뷰 데이터 부족으로 상세 분석 불가"],
    "pros": [],
    "cons": [],
    "evidence": []
}}
"""
    return prompt


async def summarize_product_with_llm(
    offer: Offer,
    additional_info: Optional[str] = None,
    reviews: Optional[List[str]] = None
) -> Dict[str, List[str]]:
    """Generate product summary using AWS Bedrock Titan.
    
    Args:
        offer: Product offer to summarize
        additional_info: Additional product specifications
        reviews: List of customer reviews
        
    Returns:
        Dictionary with key_features, pros, cons, evidence
    """
    settings = get_settings()
    
    # If Bedrock is not configured, return placeholder
    if not settings.aws_access_key_id:
        return _generate_fallback_summary(offer, reviews)
    
    prompt = build_summarize_prompt(offer, additional_info, reviews)
    
    try:
        client = get_bedrock_client()
        
        # Prepare request body for Titan
        body = json.dumps({
            "inputText": prompt,
            "textGenerationConfig": {
                "maxTokenCount": 1024,
                "temperature": 0.3,
                "topP": 0.9,
            }
        })
        
        response = client.invoke_model(
            modelId=settings.bedrock_model_id,
            contentType="application/json",
            accept="application/json",
            body=body
        )
        
        response_body = json.loads(response["body"].read())
        output_text = response_body.get("results", [{}])[0].get("outputText", "")
        
        # Parse JSON from response
        return _parse_llm_response(output_text)
        
    except ClientError as e:
        print(f"Bedrock API error: {e}")
        return _generate_fallback_summary(offer, reviews)
    except Exception as e:
        print(f"LLM summarization error: {e}")
        return _generate_fallback_summary(offer, reviews)


def _parse_llm_response(text: str) -> Dict[str, List[str]]:
    """Parse JSON response from LLM."""
    try:
        # Try to find JSON in the response
        start = text.find("{")
        end = text.rfind("}") + 1
        
        if start >= 0 and end > start:
            json_str = text[start:end]
            data = json.loads(json_str)
            
            return {
                "key_features": data.get("key_features", []),
                "pros": data.get("pros", []),
                "cons": data.get("cons", []),
                "evidence": data.get("evidence", [])
            }
    except json.JSONDecodeError:
        pass
    
    return {
        "key_features": ["응답 파싱 오류"],
        "pros": [],
        "cons": [],
        "evidence": []
    }


def _generate_fallback_summary(
    offer: Offer,
    reviews: Optional[List[str]] = None
) -> Dict[str, List[str]]:
    """Generate a basic summary when LLM is not available.

    라면 제품별 특성 데이터베이스를 활용한 분석 제공.
    """
    # 라면 제품별 특성 데이터베이스
    PRODUCT_INFO = {
        "신라면": {
            "features": ["매운맛의 대표 라면", "쇠고기 육수 베이스", "1986년 출시 스테디셀러"],
            "pros": ["진한 매운맛", "풍부한 국물", "높은 인지도", "어디서나 구매 가능"],
            "cons": ["나트륨 함량 높음", "매운맛이 강해 호불호"]
        },
        "짜파게티": {
            "features": ["짜장 라면의 원조", "올리브유 첨가", "특제 짜장 분말스프"],
            "pros": ["고소한 짜장 맛", "간편한 조리", "남녀노소 인기"],
            "cons": ["느끼할 수 있음", "국물이 없음"]
        },
        "너구리": {
            "features": ["다시마 면발", "얼큰한 국물", "쫄깃한 면"],
            "pros": ["쫄깃한 면발", "시원한 국물", "해장에 좋음"],
            "cons": ["면이 불기 쉬움", "호불호가 있는 맛"]
        },
        "진라면": {
            "features": ["순한맛/매운맛 선택", "소고기 사골 육수", "1988년 출시"],
            "pros": ["깔끔한 국물맛", "가성비 좋음", "부드러운 면발"],
            "cons": ["신라면보다 심심할 수 있음"]
        },
        "삼양라면": {
            "features": ["1963년 최초의 라면", "담백한 맛", "전통 레시피"],
            "pros": ["담백한 맛", "옛날 감성", "저렴한 가격"],
            "cons": ["자극적인 맛 선호 시 밋밋함"]
        },
        "불닭볶음면": {
            "features": ["초매운맛", "볶음면 타입", "SNS 인기 제품"],
            "pros": ["강렬한 매운맛", "중독성 있음", "다양한 맛 라인업"],
            "cons": ["너무 매워서 호불호", "물 필수"]
        },
        "팔도비빔면": {
            "features": ["비빔면의 원조", "새콤달콤한 맛", "여름 별미"],
            "pros": ["새콤달콤 상큼함", "여름에 시원하게", "간편한 조리"],
            "cons": ["겨울엔 비선호", "양이 적게 느껴짐"]
        },
        "왕뚜껑": {
            "features": ["큰 용량 컵라면", "진한 육수", "두꺼운 면발"],
            "pros": ["양이 푸짐함", "진한 국물", "휴대 간편"],
            "cons": ["칼로리 높음", "나트륨 높음"]
        },
        "안성탕면": {
            "features": ["구수한 된장맛", "한국적인 맛", "1983년 출시"],
            "pros": ["구수한 맛", "순한 맛", "한국인 입맛에 맞음"],
            "cons": ["자극적인 맛 원할 때 부족"]
        },
        "육개장": {
            "features": ["얼큰한 육개장 맛", "고추기름", "소고기 풍미"],
            "pros": ["칼칼한 맛", "해장에 좋음", "든든함"],
            "cons": ["매운맛 약한 사람 비추"]
        },
        # 오뚜기 추가 제품
        "참깨라면": {
            "features": ["참깨 풍미", "고소한 국물", "부드러운 면발"],
            "pros": ["고소한 맛", "순한 맛", "어린이도 즐길 수 있음"],
            "cons": ["자극적인 맛 원하면 부족"]
        },
        "진짜장": {
            "features": ["짜장라면", "춘장 베이스", "짜장면 맛 재현"],
            "pros": ["짜장면 맛", "간편 조리", "느끼하지 않음"],
            "cons": ["국물이 없음", "소스가 적을 수 있음"]
        },
        "열라면": {
            "features": ["매운맛 라면", "청양고추", "칼칼한 국물"],
            "pros": ["시원하고 매운맛", "해장에 좋음", "가성비 좋음"],
            "cons": ["매운맛 강함", "호불호 있음"]
        },
        "스낵면": {
            "features": ["작은 사이즈", "간식용 라면", "가벼운 한끼"],
            "pros": ["양이 적당", "간식으로 좋음", "저렴함"],
            "cons": ["양이 부족할 수 있음", "성인에겐 모자람"]
        },
        # 삼양 추가 제품
        "짜짜로니": {
            "features": ["짜장 비빔면", "달콤한 짜장", "비빔 스타일"],
            "pros": ["달콤한 맛", "아이들이 좋아함", "비빔면 스타일"],
            "cons": ["느끼할 수 있음", "국물이 없음"]
        },
        "나가사키짬뽕": {
            "features": ["짬뽕맛 라면", "해산물 풍미", "얼큰한 국물"],
            "pros": ["해물 풍미", "얼큰함", "짬뽕 맛 재현"],
            "cons": ["호불호 있음", "해산물 싫어하면 비추"]
        },
        "맛있는라면": {
            "features": ["기본에 충실", "담백한 맛", "가성비 제품"],
            "pros": ["저렴한 가격", "담백한 맛", "무난함"],
            "cons": ["특색이 없음", "밋밋할 수 있음"]
        },
        # 팔도 추가 제품
        "틈새라면": {
            "features": ["매운맛 라면", "빨간 국물", "강렬한 맛"],
            "pros": ["매운맛 강렬", "중독성", "라면 마니아 선호"],
            "cons": ["너무 매움", "초보자 비추"]
        },
        "꼬꼬면": {
            "features": ["닭고기 육수", "흰 국물 라면", "담백한 맛"],
            "pros": ["담백한 맛", "느끼하지 않음", "순한 맛"],
            "cons": ["자극적인 맛 원하면 부족", "호불호 있음"]
        },
        "일품해물라면": {
            "features": ["해물 풍미", "진한 국물", "푸짐한 건더기"],
            "pros": ["해물 맛", "국물 진함", "푸짐함"],
            "cons": ["해산물 싫어하면 비추", "가격 높음"]
        },
    }

    key_features = []
    pros = []
    cons = []
    evidence = []

    # 제품명에서 키워드 매칭
    title_lower = offer.title.lower() if offer.title else ""
    matched_product = None

    for product_name, info in PRODUCT_INFO.items():
        if product_name in title_lower or product_name.replace(" ", "") in title_lower.replace(" ", ""):
            matched_product = info
            evidence.append(f"제품 매칭: {product_name}")
            break

    # 기본 정보 추가
    if offer.price_krw:
        key_features.append(f"최저가 {offer.price_krw:,}원")
        if offer.price_krw < 700:
            pros.append("저렴한 가격")
        elif offer.price_krw > 1500:
            cons.append("다소 높은 가격")

    if offer.rating is not None:
        key_features.append(f"평점 {offer.rating:.1f}/5.0")
        if offer.rating >= 4.5:
            pros.append("높은 고객 만족도")
        elif offer.rating < 3.5:
            cons.append("평점이 다소 낮음")

    if offer.review_count:
        key_features.append(f"리뷰 {offer.review_count:,}개")
        if offer.review_count >= 1000:
            pros.append("많은 리뷰로 검증됨")

    # 제품별 정보 추가
    if matched_product:
        key_features.extend(matched_product["features"][:2])
        pros.extend(matched_product["pros"][:3])
        cons.extend(matched_product["cons"][:2])
    else:
        # 제품 매칭 안 된 경우 일반 분석
        if "컵" in title_lower or "사발" in title_lower:
            key_features.append("컵라면 타입")
            pros.append("간편한 조리")
        if "봉지" in title_lower or not ("컵" in title_lower or "사발" in title_lower):
            key_features.append("봉지면 타입")
            pros.append("가성비 좋음")

    if not key_features:
        key_features.append("상세 정보 수집 중")

    if not pros:
        pros.append("추가 분석 필요")

    return {
        "key_features": key_features[:5],
        "pros": pros[:4],
        "cons": cons[:3],
        "evidence": evidence[:3]
    }


async def enrich_product_summary(
    summary: ProductSummary,
    reviews: Optional[List[str]] = None
) -> ProductSummary:
    """Enrich a ProductSummary with LLM-generated content.
    
    Args:
        summary: ProductSummary to enrich
        reviews: Optional customer reviews
        
    Returns:
        Enriched ProductSummary
    """
    if not summary.best_offer:
        summary.key_features = ["제품 정보를 찾을 수 없습니다"]
        return summary
    
    llm_result = await summarize_product_with_llm(
        summary.best_offer,
        reviews=reviews
    )
    
    summary.key_features = llm_result["key_features"]
    summary.pros = llm_result["pros"]
    summary.cons = llm_result["cons"]
    summary.evidence = llm_result["evidence"]
    
    return summary
