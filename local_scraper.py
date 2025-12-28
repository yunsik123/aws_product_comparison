"""
로컬 스크래퍼 - 다나와에서 상품 정보를 수집하여 DynamoDB에 저장

사용법:
    python local_scraper.py                    # 기본 상품 스크래핑
    python local_scraper.py --query "신라면"   # 특정 상품 검색
    python local_scraper.py --loop 30          # 30분마다 자동 갱신
    python local_scraper.py --no-selenium      # Selenium 없이 실행 (평점/리뷰 수집 안함)
"""

import asyncio
import argparse
import time
import re
from datetime import datetime, timezone
from decimal import Decimal
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import boto3
from botocore.exceptions import ClientError

# Import local danawa scraper
from app.sources.danawa import search_danawa

# Selenium imports
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("Warning: Selenium not installed. Rating/review collection disabled.")


# Configuration
DYNAMODB_TABLE = "nongshim-product-cache"
AWS_REGION = "ap-northeast-2"
TTL_HOURS = 24  # Data expires after 24 hours

# Default products to scrape (브랜드별 라면 제품)
DEFAULT_PRODUCTS = [
    # 농심
    {"brand": "농심", "query": "신라면"},
    {"brand": "농심", "query": "신라면 컵"},
    {"brand": "농심", "query": "짜파게티"},
    {"brand": "농심", "query": "너구리"},
    {"brand": "농심", "query": "안성탕면"},
    {"brand": "농심", "query": "육개장"},
    # 오뚜기
    {"brand": "오뚜기", "query": "진라면"},
    {"brand": "오뚜기", "query": "진라면 매운맛"},
    {"brand": "오뚜기", "query": "참깨라면"},
    {"brand": "오뚜기", "query": "진짜장"},
    {"brand": "오뚜기", "query": "열라면"},
    {"brand": "오뚜기", "query": "스낵면"},
    # 삼양
    {"brand": "삼양", "query": "삼양라면"},
    {"brand": "삼양", "query": "불닭볶음면"},
    {"brand": "삼양", "query": "짜짜로니"},
    {"brand": "삼양", "query": "나가사키짬뽕"},
    {"brand": "삼양", "query": "맛있는라면"},
    # 팔도
    {"brand": "팔도", "query": "팔도비빔면"},
    {"brand": "팔도", "query": "왕뚜껑"},
    {"brand": "팔도", "query": "틈새라면"},
    {"brand": "팔도", "query": "꼬꼬면"},
    {"brand": "팔도", "query": "일품해물라면"},
]


def get_dynamodb_table():
    """Get DynamoDB table resource."""
    dynamodb = boto3.resource('dynamodb', region_name=AWS_REGION)
    return dynamodb.Table(DYNAMODB_TABLE)


class SeleniumScraper:
    """Selenium 기반 다나와 상세 정보 스크래퍼."""

    def __init__(self):
        self.driver = None

    def start(self):
        """Chrome 드라이버 시작."""
        if not SELENIUM_AVAILABLE:
            return False

        try:
            options = Options()
            options.add_argument('--headless')  # 헤드리스 모드
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            options.add_argument('--lang=ko-KR')

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            return True
        except Exception as e:
            print(f"  [Selenium] Failed to start: {e}")
            return False

    def stop(self):
        """Chrome 드라이버 종료."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
            self.driver = None

    def get_rating_and_reviews(self, url: str) -> tuple:
        """상품 상세 페이지에서 평점과 리뷰 수 추출.

        Returns:
            (rating, review_count) 튜플. 못 찾으면 (None, None)
        """
        if not self.driver:
            return None, None

        try:
            self.driver.get(url)

            # 페이지 로딩 대기 (평점/리뷰 정보가 JS로 로드됨)
            time.sleep(3)

            rating = None
            review_count = None

            # 평점 찾기 - 여러 셀렉터 시도
            rating_selectors = [
                '.star_graph .graph_value',
                '.point_num',
                '.star_score em',
                '.satisfaction_grade .grade_val',
                '.danawa_score .score_val',
                '.star_area .point',
                '.grade_num',
                '.total_grade em',
            ]

            for selector in rating_selectors:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    if text:
                        match = re.search(r'(\d+\.?\d*)', text)
                        if match:
                            val = float(match.group(1))
                            # 100점 만점이면 5점으로 변환
                            if val > 5:
                                val = val / 20.0
                            rating = min(5.0, max(0.0, round(val, 1)))
                            break
                except:
                    continue

            # 리뷰 수 찾기 - 여러 셀렉터 시도
            review_selectors = [
                '.cnt_opinion a',
                '.danawa_review_num',
                '.cmt_num',
                '.review_cnt',
                '.user_review_count',
                '#danawa-prodBlog-companyReview-button-tab-productOpinion',
                'a[name="productOpinion"] .cnt',
            ]

            for selector in review_selectors:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    text = elem.text.strip()
                    if text:
                        # 숫자만 추출
                        nums = re.sub(r'[^\d]', '', text)
                        if nums:
                            review_count = int(nums)
                            break
                except:
                    continue

            # 탭에서 상품평/리뷰 수 찾기 (예: "의견/평가 61,771")
            try:
                tabs = self.driver.find_elements(By.CSS_SELECTOR, '.prod_tap li a, .tab_list li a, nav a')
                for tab in tabs:
                    text = tab.text.strip()
                    # "의견/평가", "상품평", "리뷰" 등이 포함된 탭에서 숫자 추출
                    if '의견' in text or '평가' in text or '상품평' in text or '리뷰' in text:
                        # 쉼표 포함된 숫자 추출 (예: 61,771)
                        nums = re.sub(r'[^\d,]', '', text)
                        nums = nums.replace(',', '')
                        if nums:
                            val = int(nums)
                            current = review_count or 0
                            if val > current:
                                review_count = val
            except:
                pass

            # 쇼핑몰 리뷰 수도 확인 (더 큰 숫자 사용)
            try:
                mall_review = self.driver.find_elements(By.XPATH, "//*[contains(text(), '상품리뷰') or contains(text(), '쇼핑몰')]")
                for elem in mall_review:
                    text = elem.text.strip()
                    nums = re.sub(r'[^\d,]', '', text)
                    nums = nums.replace(',', '')
                    if nums:
                        val = int(nums)
                        current = review_count or 0
                        if val > current:
                            review_count = val
            except:
                pass

            return rating, review_count

        except Exception as e:
            print(f"  [Selenium] Error: {e}")
            return None, None


def convert_to_dynamodb_format(data):
    """Convert Python types to DynamoDB compatible types."""
    if isinstance(data, float):
        return Decimal(str(data))
    elif isinstance(data, dict):
        return {k: convert_to_dynamodb_format(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_to_dynamodb_format(i) for i in data]
    return data


async def scrape_and_store(brand: str, query: str, table, selenium_scraper=None) -> dict:
    """Scrape product data and store in DynamoDB."""
    print(f"  Scraping: {brand} {query}...", end=" ", flush=True)

    try:
        # Scrape from Danawa
        offers = await search_danawa(query, brand, max_results=10)

        if not offers:
            print("No results")
            return {"brand": brand, "query": query, "status": "no_results", "count": 0}

        # Selenium으로 첫 번째 상품의 평점/리뷰 수 가져오기
        rating = None
        review_count = None
        if selenium_scraper and offers[0].url:
            rating, review_count = selenium_scraper.get_rating_and_reviews(offers[0].url)

        # Prepare data for DynamoDB
        now = datetime.now(timezone.utc)
        ttl_timestamp = int(now.timestamp()) + (TTL_HOURS * 3600)

        # Convert offers to dict
        offers_data = []
        for i, offer in enumerate(offers):
            offer_dict = {
                "source": offer.source,
                "title": offer.title,
                "url": offer.url,
                "price_krw": offer.price_krw,
                "rating": float(rating) if (i == 0 and rating) else (float(offer.rating) if offer.rating else None),
                "review_count": review_count if (i == 0 and review_count) else offer.review_count,
                "image_url": offer.image_url,
                "fetched_at": offer.fetched_at
            }
            offers_data.append(offer_dict)

        # Create item
        item = {
            "pk": f"PRODUCT#{brand}",
            "sk": f"QUERY#{query}",
            "brand": brand,
            "query": query,
            "offers": convert_to_dynamodb_format(offers_data),
            "offer_count": len(offers),
            "updated_at": now.isoformat(),
            "ttl": ttl_timestamp
        }

        # Store best offer separately for quick access
        if offers:
            best = offers[0]
            item["best_price"] = best.price_krw
            item["best_title"] = best.title
            item["best_rating"] = convert_to_dynamodb_format(rating if rating else best.rating)
            item["best_review_count"] = review_count

        # Store in DynamoDB
        table.put_item(Item=item)

        # 결과 메시지
        rating_str = f"{rating:.1f}" if rating else "N/A"
        review_str = f"{review_count:,}" if review_count else "N/A"
        print(f"OK ({len(offers)} offers, {item.get('best_price', 'N/A')}원, ★{rating_str}, 리뷰 {review_str})")

        return {"brand": brand, "query": query, "status": "success", "count": len(offers),
                "rating": rating, "review_count": review_count}

    except Exception as e:
        print(f"Error: {e}")
        return {"brand": brand, "query": query, "status": "error", "error": str(e)}


async def run_scraper(products: list, table, use_selenium: bool = True):
    """Run scraper for all products."""
    print(f"\n{'='*50}")
    print(f"Starting scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    # Selenium 초기화
    selenium_scraper = None
    if use_selenium and SELENIUM_AVAILABLE:
        print("  [Selenium] Starting Chrome driver...")
        selenium_scraper = SeleniumScraper()
        if not selenium_scraper.start():
            print("  [Selenium] Failed to start, continuing without rating/review data")
            selenium_scraper = None
        else:
            print("  [Selenium] Chrome driver ready\n")

    results = []
    try:
        for product in products:
            result = await scrape_and_store(
                product["brand"], product["query"], table, selenium_scraper
            )
            results.append(result)
            # Small delay between requests
            await asyncio.sleep(1)
    finally:
        # Selenium 종료
        if selenium_scraper:
            selenium_scraper.stop()
            print("\n  [Selenium] Chrome driver stopped")

    # Summary
    success = sum(1 for r in results if r["status"] == "success")
    with_rating = sum(1 for r in results if r.get("rating") is not None)
    total = len(results)
    print(f"\n{'='*50}")
    print(f"Completed: {success}/{total} products scraped")
    print(f"Rating/Review data: {with_rating}/{success} products")
    print(f"{'='*50}\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="Local Danawa scraper with DynamoDB storage")
    parser.add_argument("--query", type=str, help="Specific product query to scrape")
    parser.add_argument("--brand", type=str, default="농심", help="Brand name (default: 농심)")
    parser.add_argument("--loop", type=int, help="Run continuously every N minutes")
    parser.add_argument("--list", action="store_true", help="List current data in DynamoDB")
    parser.add_argument("--no-selenium", action="store_true", help="Disable Selenium (skip rating/review)")
    args = parser.parse_args()

    use_selenium = not args.no_selenium

    # Get DynamoDB table
    try:
        table = get_dynamodb_table()
        # Test connection
        table.table_status
        print(f"Connected to DynamoDB table: {DYNAMODB_TABLE}")
    except ClientError as e:
        print(f"Error connecting to DynamoDB: {e}")
        print("\nMake sure to run setup_dynamodb.ps1 first!")
        sys.exit(1)

    # List mode
    if args.list:
        print("\nCurrent data in DynamoDB:")
        print("-" * 60)
        response = table.scan()
        for item in response.get('Items', []):
            print(f"  {item['brand']} {item['query']}: {item.get('offer_count', 0)} offers, "
                  f"best: {item.get('best_price', 'N/A')}원, "
                  f"updated: {item.get('updated_at', 'N/A')}")
        return

    # Determine products to scrape
    if args.query:
        products = [{"brand": args.brand, "query": args.query}]
    else:
        products = DEFAULT_PRODUCTS

    # Run scraper
    if args.loop:
        print(f"Running in loop mode (every {args.loop} minutes)")
        if use_selenium:
            print("Selenium enabled - collecting rating/review data")
        print("Press Ctrl+C to stop\n")
        try:
            while True:
                asyncio.run(run_scraper(products, table, use_selenium))
                print(f"Next run in {args.loop} minutes...")
                time.sleep(args.loop * 60)
        except KeyboardInterrupt:
            print("\nStopped by user")
    else:
        asyncio.run(run_scraper(products, table, use_selenium))


if __name__ == "__main__":
    main()
