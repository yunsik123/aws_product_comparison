"""다나와 웹스크래핑 connector (API 키 불필요) - 개선된 버전."""
import httpx
import re
from typing import List, Optional, Tuple, Dict, Any
from bs4 import BeautifulSoup
from dataclasses import dataclass

from ..schemas import Offer
from ..utils import get_current_iso_datetime, safe_int, safe_float, normalize_rating


DANAWA_SEARCH_URL = "https://search.danawa.com/dsearch.php"
DANAWA_PRODUCT_URL = "https://prod.danawa.com/info/"
DANAWA_REVIEW_API = "https://prod.danawa.com/info/dpg/ajax/companyProductReview.ajax.php"


@dataclass
class Review:
    """리뷰 데이터 클래스."""
    text: str
    rating: Optional[float] = None
    mall: Optional[str] = None  # 쇼핑몰명
    date: Optional[str] = None
    has_photo: bool = False


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


async def get_product_reviews(
    pcode: str,
    max_reviews: int = 100,
    sort_type: str = "new"
) -> Tuple[List[Review], float, int]:
    """상품 리뷰 수집.

    Args:
        pcode: 다나와 상품 코드
        max_reviews: 최대 수집 리뷰 수 (기본 100)
        sort_type: 정렬 방식 - "new" (최신순), "best" (추천순)

    Returns:
        (리뷰 목록, 평균 평점, 전체 리뷰 수) 튜플
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": f"https://prod.danawa.com/info/?pcode={pcode}",
    }

    reviews: List[Review] = []
    avg_rating: float = 0.0
    total_count: int = 0
    page = 1
    per_page = 30  # 다나와 API 최대값

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            while len(reviews) < max_reviews:
                params = {
                    "prodCode": pcode,
                    "page": page,
                    "limit": per_page,
                    "score": 0,  # 0 = 전체, 1-5 = 해당 점수만
                    "sortType": sort_type,
                }

                resp = await client.get(DANAWA_REVIEW_API, params=params, headers=headers)
                if resp.status_code != 200:
                    break

                soup = BeautifulSoup(resp.text, 'html.parser')

                # 첫 페이지에서 평점/전체 리뷰 수 추출
                if page == 1:
                    rating_elem = soup.select_one('.point_num .num_c, .point_num strong')
                    if rating_elem:
                        try:
                            avg_rating = float(rating_elem.get_text(strip=True))
                        except ValueError:
                            pass

                    count_elem = soup.select_one('.cen_w .num_c, .cen_w strong')
                    if count_elem:
                        try:
                            count_text = count_elem.get_text(strip=True).replace(',', '')
                            total_count = int(count_text)
                        except ValueError:
                            pass

                # 리뷰 파싱
                review_items = soup.select('.cmt_item, .danawa-prodBlog-companyReview-clazz-more')
                if not review_items:
                    # 다른 구조 시도
                    review_items = soup.select('li[class*="cmt"]')

                if not review_items:
                    break

                for item in review_items:
                    if len(reviews) >= max_reviews:
                        break

                    # 리뷰 텍스트
                    text_elem = item.select_one('.atc')
                    if not text_elem:
                        continue
                    text = text_elem.get_text(strip=True)
                    if not text or len(text) < 3:
                        continue

                    # 평점 (개별 리뷰)
                    rating = None
                    star_elem = item.select_one('.star_mask, .point_type_s .star_mask')
                    if star_elem:
                        style = star_elem.get('style', '')
                        width_match = re.search(r'width:\s*(\d+)%', style)
                        if width_match:
                            rating = float(width_match.group(1)) / 20.0  # 100% = 5점

                    # 쇼핑몰명
                    mall = None
                    mall_elem = item.select_one('.mall_txt, .mall_name, .info_cell a')
                    if mall_elem:
                        mall = mall_elem.get_text(strip=True)

                    # 날짜
                    date = None
                    date_elem = item.select_one('.date, .info_date')
                    if date_elem:
                        date = date_elem.get_text(strip=True)

                    # 포토 리뷰 여부
                    has_photo = bool(item.select_one('.ico.i_photo_review, .photo_review, img.review_img'))

                    reviews.append(Review(
                        text=text[:500],  # 최대 500자
                        rating=rating,
                        mall=mall,
                        date=date,
                        has_photo=has_photo
                    ))

                # 다음 페이지
                page += 1

                # 더 이상 리뷰가 없으면 종료
                if len(review_items) < per_page:
                    break

    except Exception as e:
        print(f"Error fetching reviews: {e}")

    return reviews, avg_rating, total_count


async def get_reviews_by_query(
    query: str,
    brand: Optional[str] = None,
    max_reviews: int = 100
) -> Tuple[List[Review], float, int, str]:
    """검색어로 상품 찾아서 리뷰 수집.

    Returns:
        (리뷰 목록, 평균 평점, 전체 리뷰 수, 상품 URL) 튜플
    """
    # 먼저 상품 검색해서 pcode 추출
    search_query = f"{brand} {query}" if brand else query

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            params = {"keyword": search_query, "module": "goods"}
            resp = await client.get(DANAWA_SEARCH_URL, params=params, headers=headers)
            soup = BeautifulSoup(resp.text, 'html.parser')

            # 첫 번째 상품 URL에서 pcode 추출
            prod_link = soup.select_one('.prod_name a')
            if not prod_link:
                return [], 0.0, 0, ""

            prod_url = prod_link.get('href', '')
            pcode_match = re.search(r'pcode=(\d+)', prod_url)
            if not pcode_match:
                return [], 0.0, 0, ""

            pcode = pcode_match.group(1)
            reviews, avg_rating, total_count = await get_product_reviews(pcode, max_reviews)

            return reviews, avg_rating, total_count, prod_url

    except Exception as e:
        print(f"Error in get_reviews_by_query: {e}")
        return [], 0.0, 0, ""
