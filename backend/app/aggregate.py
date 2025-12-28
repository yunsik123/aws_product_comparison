"""Aggregate results from data sources - 다나와 스크래핑 전용."""
import asyncio
from typing import List, Dict, Optional, Tuple

from .schemas import Offer, ProductSummary, Comparison
from .sources import search_danawa
from .normalize import match_offers_for_product


# Source name to function mapping - 다나와만 사용
SOURCE_FUNCTIONS = {
    "danawa": search_danawa,
}


async def fetch_from_sources(
    query: str,
    brand: str,
    sources: List[str],
    max_results: int = 10
) -> Tuple[List[Offer], List[str]]:
    """Fetch product data from multiple sources in parallel.
    
    Args:
        query: Product search query
        brand: Brand name
        sources: List of source names to query
        max_results: Max results per source
        
    Returns:
        Tuple of (all_offers, warnings)
    """
    all_offers = []
    warnings = []
    
    # Create tasks for enabled sources
    tasks = []
    source_names = []
    
    for source in sources:
        if source in SOURCE_FUNCTIONS:
            func = SOURCE_FUNCTIONS[source]
            tasks.append(func(query, brand, max_results))
            source_names.append(source)
        else:
            warnings.append(f"Unknown source: {source}")
    
    if not tasks:
        return [], ["No valid sources specified"]
    
    # Run all tasks in parallel
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for source_name, result in zip(source_names, results):
        if isinstance(result, Exception):
            warnings.append(f"Error from {source_name}: {str(result)}")
        elif result:
            all_offers.extend(result)
        else:
            warnings.append(f"No results from {source_name}")
    
    return all_offers, warnings


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
