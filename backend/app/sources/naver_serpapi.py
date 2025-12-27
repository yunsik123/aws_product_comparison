"""Naver Shopping search via SerpApi connector."""
import httpx
from typing import List, Optional

from ..schemas import Offer
from ..config import get_settings
from ..utils import get_current_iso_datetime, safe_int, safe_float, normalize_rating


SERPAPI_URL = "https://serpapi.com/search"


async def search_naver_serpapi(
    query: str,
    brand: Optional[str] = None,
    max_results: int = 10
) -> List[Offer]:
    """Search products on Naver Shopping using SerpApi.
    
    Args:
        query: Search query (product name)
        brand: Brand name to include in search
        max_results: Maximum number of results to return
        
    Returns:
        List of Offer objects
    """
    settings = get_settings()
    
    if not settings.serpapi_api_key:
        return []
    
    search_query = f"{brand} {query}" if brand else query
    
    params = {
        "engine": "naver_shopping",
        "query": search_query,
        "api_key": settings.serpapi_api_key,
        "num": max_results,
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(SERPAPI_URL, params=params)
            response.raise_for_status()
            
            return _parse_serpapi_response(response.json())
    except httpx.HTTPError as e:
        print(f"SerpApi error: {e}")
        return []
    except Exception as e:
        print(f"SerpApi parsing error: {e}")
        return []


def _parse_serpapi_response(data: dict) -> List[Offer]:
    """Parse SerpApi Naver Shopping response."""
    offers = []
    fetched_at = get_current_iso_datetime()
    
    shopping_results = data.get("shopping_results", [])
    
    for item in shopping_results:
        title = item.get("title", "")
        if not title:
            continue
        
        # Extract price (remove currency symbols and commas)
        price_str = item.get("price", "")
        if isinstance(price_str, str):
            price_str = price_str.replace("원", "").replace(",", "").strip()
        
        offer = Offer(
            source="naver_serpapi",
            title=title,
            url=item.get("link", ""),
            price_krw=safe_int(price_str),
            rating=normalize_rating(safe_float(item.get("rating"))),
            review_count=safe_int(item.get("reviews")),
            image_url=item.get("thumbnail"),
            fetched_at=fetched_at
        )
        offers.append(offer)
    
    return offers
