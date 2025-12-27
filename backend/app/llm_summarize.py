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
    """Generate a basic summary when LLM is not available."""
    key_features = []
    
    # Extract basic features from offer
    if offer.price_krw:
        key_features.append(f"가격: {offer.price_krw:,}원")
    
    if offer.rating is not None:
        key_features.append(f"평점: {offer.rating}/5.0")
    
    if offer.review_count:
        key_features.append(f"리뷰: {offer.review_count}개")
    
    if not key_features:
        key_features.append("상세 정보 수집 불가")
    
    return {
        "key_features": key_features,
        "pros": ["LLM 분석 불가 - API 키 설정 필요"],
        "cons": [],
        "evidence": []
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
