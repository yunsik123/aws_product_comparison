"""Aggregate results from data sources - DynamoDB 캐시 우선, 로컬은 다나와 스크래핑."""
import asyncio
import os
from typing import List, Dict, Optional, Tuple

from .schemas import Offer, ProductSummary, Comparison
from .sources import search_danawa
from .normalize import match_offers_for_product


# Check if running in Lambda (use DynamoDB) or local (use direct scraping)
IS_LAMBDA = os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None
USE_DYNAMODB = os.getenv("USE_DYNAMODB", "true").lower() == "true"


async def fetch_from_dynamodb(query: str, brand: str) -> Tuple[List[Offer], bool]:
    """Fetch from DynamoDB cache."""
    try:
        from .dynamodb_client import get_cached_offers
        return await get_cached_offers(brand, query)
    except Exception as e:
        print(f"DynamoDB fetch error: {e}")
        return [], False


async def fetch_from_sources(
    query: str,
    brand: str,
    sources: List[str],
    max_results: int = 10
) -> Tuple[List[Offer], List[str]]:
    """Fetch product data - from DynamoDB (Lambda) or direct scraping (local).

    Args:
        query: Product search query
        brand: Brand name
        sources: List of source names to query
        max_results: Max results per source

    Returns:
        Tuple of (all_offers, warnings)
    """
    warnings = []

    # Lambda environment: use DynamoDB cache
    if IS_LAMBDA or USE_DYNAMODB:
        offers, from_cache = await fetch_from_dynamodb(query, brand)
        if offers:
            return offers, [f"Data from DynamoDB cache ({len(offers)} offers)"]
        else:
            warnings.append("No cached data in DynamoDB. Run local_scraper.py to populate.")
            # Don't try direct scraping in Lambda (blocked by Danawa)
            if IS_LAMBDA:
                return [], warnings

    # Local environment: direct scraping
    try:
        offers = await search_danawa(query, brand, max_results)
        if offers:
            return offers, ["Data from direct Danawa scraping"]
        else:
            warnings.append("No results from Danawa scraping")
            return [], warnings
    except Exception as e:
        warnings.append(f"Scraping error: {str(e)}")
        return [], warnings


async def aggregate_product_data(
    query: str,
    brand: str,
    sources: List[str]
) -> Tuple[ProductSummary, List[str]]:
    """Aggregate product data from multiple sources.
    
    Args:
        query: Product search query
        brand: Brand name
        sources: List of source names
        
    Returns:
        Tuple of (ProductSummary, warnings)
    """
    # Fetch from all sources
    offers, fetch_warnings = await fetch_from_sources(query, brand, sources)
    
    # Match and rank offers
    best_offer, sorted_offers, match_warnings = match_offers_for_product(
        offers, query, brand
    )
    
    # Combine warnings
    all_warnings = fetch_warnings + match_warnings
    
    # Create ProductSummary (LLM fields will be filled later)
    summary = ProductSummary(
        brand=brand,
        query=query,
        best_offer=best_offer,
        offers=sorted_offers,
        key_features=[],
        pros=[],
        cons=[],
        sentiment=None,
        evidence=[]
    )
    
    return summary, all_warnings


def calculate_comparison(
    product_a: ProductSummary,
    product_b: ProductSummary
) -> Comparison:
    """Calculate comparison metrics between two products.
    
    Args:
        product_a: First product summary
        product_b: Second product summary
        
    Returns:
        Comparison object with differences
    """
    rating_diff = None
    price_diff = None
    review_diff = None
    
    # Get ratings from best offers
    if product_a.best_offer and product_b.best_offer:
        rating_a = product_a.best_offer.rating
        rating_b = product_b.best_offer.rating
        if rating_a is not None and rating_b is not None:
            rating_diff = round(rating_a - rating_b, 2)
        
        price_a = product_a.best_offer.price_krw
        price_b = product_b.best_offer.price_krw
        if price_a is not None and price_b is not None:
            price_diff = price_a - price_b
        
        review_a = product_a.best_offer.review_count
        review_b = product_b.best_offer.review_count
        if review_a is not None and review_b is not None:
            review_diff = review_a - review_b
    
    return Comparison(
        rating_diff=rating_diff,
        price_diff_krw=price_diff,
        review_count_diff=review_diff
    )
