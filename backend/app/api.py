"""FastAPI router for product comparison API."""
import json
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime

from .schemas import CompareRequest, CompareResponse, HealthResponse
from .aggregate import aggregate_product_data, calculate_comparison
from .llm_summarize import enrich_product_summary
from .cache import get_cache, get_rate_limiter, make_cache_key
from .utils import generate_request_id
from .config import get_settings


router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat()
    )


@router.post("/compare", response_model=CompareResponse, tags=["Compare"])
async def compare_products(request: CompareRequest):
    """Compare two products from various data sources.
    
    1. Fetches product data from specified sources in parallel
    2. Normalizes and ranks offers
    3. Generates LLM-based summaries
    4. Returns comparison with cached results
    """
    settings = get_settings()
    cache = get_cache()
    rate_limiter = get_rate_limiter()
    
    # Create cache key
    cache_key = make_cache_key(
        request.brand_a,
        request.product_a,
        request.brand_b,
        request.product_b,
        request.sources
    )
    
    # Check rate limit for force refresh
    if request.force_refresh:
        allowed, wait_seconds = rate_limiter.check_and_update(cache_key)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded. Please wait {wait_seconds} seconds before force refresh."
            )
    
    # Check cache if not force refresh
    if not request.force_refresh:
        cached_result = cache.get(cache_key)
        if cached_result:
            try:
                result = CompareResponse.model_validate_json(cached_result)
                result.cached = True
                return result
            except Exception:
                pass  # Cache corrupted, fetch fresh
    
    warnings = []
    
    # Aggregate data for product A
    summary_a, warnings_a = await aggregate_product_data(
        query=request.product_a,
        brand=request.brand_a,
        sources=request.sources
    )
    warnings.extend(warnings_a)
    
    # Aggregate data for product B
    summary_b, warnings_b = await aggregate_product_data(
        query=request.product_b,
        brand=request.brand_b,
        sources=request.sources
    )
    warnings.extend(warnings_b)
    
    # Enrich with LLM summaries
    summary_a = await enrich_product_summary(summary_a)
    summary_b = await enrich_product_summary(summary_b)
    
    # Calculate comparison metrics
    comparison = calculate_comparison(summary_a, summary_b)
    
    # Build response
    response = CompareResponse(
        request_id=generate_request_id(),
        product_a=summary_a,
        product_b=summary_b,
        comparison=comparison,
        warnings=warnings,
        cached=False
    )
    
    # Store in cache
    cache.set(
        cache_key,
        response.model_dump_json(),
        ttl=settings.cache_ttl_seconds
    )
    
    return response
