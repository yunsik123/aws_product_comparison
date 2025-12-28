"""다나와 웹스크래핑 connector (API 키 불필요) - 개선된 버전."""
import httpx
import re
from typing import List, Optional, Tuple
from bs4 import BeautifulSoup

from ..schemas import Offer
from ..utils import get_current_iso_datetime, safe_int, safe_float, normalize_rating


DANAWA_SEARCH_URL = "https://search.danawa.com/dsearch.php"
DANAWA_PRODUCT_URL = "https://prod.danawa.com/info/"


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
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.danawa.com/",
        "Connection": "keep-alive",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            response = await client.get(
                DANAWA_SEARCH_URL,
                params=params,
                headers=headers
            )
            response.raise_for_status()

            offers = _parse_danawa_html(response.text, max_results)

            # 첫 번째 상품의 상세 정보 가져오기 (평점, 리뷰 수)
            if offers and offers[0].url:
                detailed_info = await _get_product_details(client, offers[0].url, headers)
                if detailed_info:
                    rating, review_count = detailed_info
                    offers[0] = Offer(
                        source=offers[0].source,
                        title=offers[0].title,
                        url=offers[0].url,
                        price_krw=offers[0].price_krw,
                        rating=rating if rating else offers[0].rating,
                        review_count=review_count if review_count else offers[0].review_count,
                        image_url=offers[0].image_url,
                        fetched_at=offers[0].fetched_at
                    )

            return offers
    except httpx.HTTPError as e:
        print(f"Danawa scrape error: {e}")
        return []
    except Exception as e:
        print(f"Danawa parsing error: {e}")
        return []


async def _get_product_details(
    client: httpx.AsyncClient,
    url: str,
    headers: dict
) -> Optional[Tuple[float, int]]:
    """상품 상세 페이지에서 평점과 리뷰 수 가져오기."""
    try:
        response = await client.get(url, headers=headers, timeout=10.0)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        rating = None
        review_count = None

        # 평점 찾기 - 여러 셀렉터 시도
        rating_selectors = [
            '.star_graph .graph_value',
            '.point_num',
            '.star_score em',
            '.satisfaction_grade .grade_val',
            '.danawa_score .score_val',
            '[class*="rating"] [class*="value"]',
            '[class*="score"] em',
        ]

        for selector in rating_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # 숫자 추출
                match = re.search(r'(\d+\.?\d*)', text)
                if match:
                    val = float(match.group(1))
                    # 100점 만점이면 5점으로 변환
                    if val > 5:
                        val = val / 20.0
                    rating = min(5.0, max(0.0, val))
                    break

        # 리뷰 수 찾기 - 여러 셀렉터 시도
        review_selectors = [
            '.cnt_opinion a',
            '.danawa_review_num',
            '.cmt_num',
            '.review_cnt',
            '[class*="review"] [class*="count"]',
            '[class*="opinion"] [class*="cnt"]',
            '.user_review_wrap .num',
            'a[href*="opinion"] span',
        ]

        for selector in review_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                # 숫자만 추출
                nums = re.sub(r'[^\d]', '', text)
                if nums:
                    review_count = int(nums)
                    break

        # 추가: 상품평 탭에서 리뷰 수 찾기
        if not review_count:
            tab_elem = soup.select_one('[data-tab-name="opinion"] .cnt, .tab_item[data-tab="opinion"] .num')
            if tab_elem:
                text = tab_elem.get_text(strip=True)
                nums = re.sub(r'[^\d]', '', text)
                if nums:
                    review_count = int(nums)

        return (rating, review_count) if (rating or review_count) else None

    except Exception as e:
        print(f"Error getting product details: {e}")
        return None


def _parse_danawa_html(html: str, max_results: int = 10) -> List[Offer]:
    """Parse 다나와 search results HTML."""
    offers = []
    fetched_at = get_current_iso_datetime()

    try:
        soup = BeautifulSoup(html, 'html.parser')

        # 여러 셀렉터 시도
        product_items = soup.select('.product_list .prod_item')

        if not product_items:
            product_items = soup.select('.main_prodlist .prod_item')

        if not product_items:
            product_items = soup.select('li.prod_item')

        if not product_items:
            product_items = soup.select('.prod_main_info')

        for item in product_items[:max_results]:
            try:
                # Product title - 여러 셀렉터 시도
                title_elem = None
                for selector in ['.prod_name a', '.prod_tit a', 'a.prod_name', 'p.prod_name a']:
                    title_elem = item.select_one(selector)
                    if title_elem:
                        break

                if not title_elem:
                    continue

                title = title_elem.get_text(strip=True)
                url = title_elem.get('href', '')

                if url and not url.startswith('http'):
                    url = 'https://prod.danawa.com' + url

                # Price - 여러 셀렉터 시도
                price_krw = None
                for selector in ['.price_sect strong', '.prod_pricelist .price_sect em',
                               '.lowest_price em', 'p.price_sect strong', '.price em']:
                    price_elem = item.select_one(selector)
                    if price_elem:
                        price_text = price_elem.get_text(strip=True)
                        price_text = re.sub(r'[^\d]', '', price_text)
                        price_krw = safe_int(price_text)
                        if price_krw and price_krw > 0:
                            break

                # Rating - 여러 셀렉터 시도
                rating = None
                for selector in ['.star_graph .graph_value', '.point_num', '.star_score em']:
                    rating_elem = item.select_one(selector)
                    if rating_elem:
                        rating_text = rating_elem.get_text(strip=True)
                        rating = safe_float(rating_text)
                        if rating and rating > 5:
                            rating = rating / 20.0
                        rating = normalize_rating(rating)
                        if rating:
                            break

                # Review count - 여러 셀렉터 시도
                review_count = None
                for selector in ['.cnt_opinion a', '.danawa_review_num', '.cmt_num',
                               'a[name="productOpinion"]', '.txt_cnt']:
                    review_elem = item.select_one(selector)
                    if review_elem:
                        review_text = review_elem.get_text(strip=True)
                        review_text = re.sub(r'[^\d]', '', review_text)
                        review_count = safe_int(review_text)
                        if review_count:
                            break

                # Image - 여러 셀렉터 시도
                image_url = None
                for selector in ['.thumb_image img', '.prod_img img', 'img.thumb', '.thumb img']:
                    img_elem = item.select_one(selector)
                    if img_elem:
                        image_url = img_elem.get('data-original') or img_elem.get('data-src') or img_elem.get('src')
                        if image_url:
                            if image_url.startswith('//'):
                                image_url = 'https:' + image_url
                            break

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
