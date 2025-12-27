"""11번가 Open API connector."""
import httpx
from typing import List, Optional
from xml.etree import ElementTree

from ..schemas import Offer
from ..config import get_settings
from ..utils import get_current_iso_datetime, safe_int, safe_float, normalize_rating


ELEVENST_API_URL = "http://openapi.11st.co.kr/openapi/OpenApiService.tmall"


async def search_elevenst(
    query: str,
    brand: Optional[str] = None,
    max_results: int = 10
) -> List[Offer]:
    """Search products on 11번가 using Open API.
    
    Args:
        query: Search query (product name)
        brand: Brand name to include in search
        max_results: Maximum number of results to return
        
    Returns:
        List of Offer objects
    """
    settings = get_settings()
    
    if not settings.elevenst_api_key:
        return []
    
    search_query = f"{brand} {query}" if brand else query
    
    params = {
        "key": settings.elevenst_api_key,
        "apiCode": "ProductSearch",
        "keyword": search_query,
        "pageSize": str(max_results),
        "pageNum": "1",
        "sortCd": "CP",  # Sort by popularity
    }
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(ELEVENST_API_URL, params=params)
            response.raise_for_status()
            
            return _parse_elevenst_response(response.text)
    except httpx.HTTPError as e:
        print(f"11st API error: {e}")
        return []
    except Exception as e:
        print(f"11st parsing error: {e}")
        return []


def _parse_elevenst_response(xml_text: str) -> List[Offer]:
    """Parse 11번가 API XML response."""
    offers = []
    fetched_at = get_current_iso_datetime()
    
    try:
        root = ElementTree.fromstring(xml_text)
        
        # Find all product elements
        products = root.findall(".//Product")
        
        for product in products:
            title = _get_text(product, "ProductName", "")
            if not title:
                continue
                
            offer = Offer(
                source="11st",
                title=title,
                url=_get_text(product, "DetailPageUrl", ""),
                price_krw=safe_int(_get_text(product, "SalePrice")),
                rating=normalize_rating(safe_float(_get_text(product, "Rating"))),
                review_count=safe_int(_get_text(product, "ReviewCount")),
                image_url=_get_text(product, "ProductImage"),
                fetched_at=fetched_at
            )
            offers.append(offer)
            
    except ElementTree.ParseError as e:
        print(f"XML parse error: {e}")
    
    return offers


def _get_text(element: ElementTree.Element, tag: str, default: str = None) -> Optional[str]:
    """Get text content from XML element."""
    child = element.find(tag)
    if child is not None and child.text:
        return child.text.strip()
    return default
