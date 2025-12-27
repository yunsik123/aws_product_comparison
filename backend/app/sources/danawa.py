"""다나와 웹스크래핑 connector (API 키 불필요)."""
import httpx
import re
from typing import List, Optional
from bs4 import BeautifulSoup

from ..schemas import Offer
from ..utils import get_current_iso_datetime, safe_int, safe_float, normalize_rating


DANAWA_SEARCH_URL = "https://search.danawa.com/dsearch.php"


async def search_danawa(
    query: str,
    brand: Optional[str] = None,
    max_results: int = 10
) -> List[Offer]:
    """Search products on 다나와 using web scraping.
    
    Args:
        query: Search query (product name)
        brand: Brand name to include in search
        max_results: Maximum number of results to return
        
    Returns:
        List of Offer objects
    """
    search_query = f"{brand} {query}" if brand else query
    
    params = {
        "keyword": search_query,
        "module": "goods",
        "act": "dispMain",
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.danawa.com/",
    }
    
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            response = await client.get(
                DANAWA_SEARCH_URL,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            
            return _parse_danawa_html(response.text, max_results)
    except httpx.HTTPError as e:
        print(f"Danawa scrape error: {e}")
        return []
    except Exception as e:
        print(f"Danawa parsing error: {e}")
        return []


def _parse_danawa_html(html: str, max_results: int = 10) -> List[Offer]:
    """Parse 다나와 search results HTML."""
    offers = []
    fetched_at = get_current_iso_datetime()
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Find product list items
        product_items = soup.select('.product_list .prod_item, .main_prodlist .prod_item, .product_list li.prod_main_info')
        
        if not product_items:
            # Alternative selector
            product_items = soup.select('.prod_main_info')
        
        for item in product_items[:max_results]:
            try:
                # Product title
                title_elem = item.select_one('.prod_name a, .prod_tit a, a.prod_name')
                if not title_elem:
                    continue
                
                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')
                
                if url and not url.startswith('http'):
                    url = 'https://prod.danawa.com' + url
                
                # Price
                price_elem = item.select_one('.price_sect strong, .prod_pricelist .price_sect em, .lowest_price em')
                price_krw = None
                if price_elem:
                    price_text = price_elem.get_text(strip=True)
                    price_text = re.sub(r'[^\d]', '', price_text)
                    price_krw = safe_int(price_text)
                
                # Rating (if available)
                rating_elem = item.select_one('.star_graph .graph_value, .point_num')
                rating = None
                if rating_elem:
                    rating_text = rating_elem.get_text(strip=True)
                    rating = safe_float(rating_text)
                    if rating and rating > 5:
                        # Convert from percentage to 5-point scale
                        rating = rating / 20.0
                    rating = normalize_rating(rating)
                
                # Review count
                review_elem = item.select_one('.cnt_opinion a, .danawa_review_num, .cmt_num')
                review_count = None
                if review_elem:
                    review_text = review_elem.get_text(strip=True)
                    review_text = re.sub(r'[^\d]', '', review_text)
                    review_count = safe_int(review_text)
                
                # Image
                img_elem = item.select_one('.thumb_image img, .prod_img img, img.thumb')
                image_url = None
                if img_elem:
                    image_url = img_elem.get('data-original') or img_elem.get('src')
                    if image_url and image_url.startswith('//'):
                        image_url = 'https:' + image_url
                
                if title:
                    offer = Offer(
                        source="danawa",
                        title=title,
                        url=url or "",
                        price_krw=price_krw,
                        rating=rating,
                        review_count=review_count,
                        image_url=image_url,
                        fetched_at=fetched_at
                    )
                    offers.append(offer)
                    
            except Exception as e:
                print(f"Error parsing product item: {e}")
                continue
                
    except Exception as e:
        print(f"HTML parse error: {e}")
    
    return offers
