"""
로컬 스크래퍼 - 다나와에서 상품 정보를 수집하여 DynamoDB에 저장

사용법:
    python local_scraper.py                    # 기본 상품 스크래핑
    python local_scraper.py --query "신라면"   # 특정 상품 검색
    python local_scraper.py --loop 30          # 30분마다 자동 갱신
"""

import asyncio
import argparse
import time
import json
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


def convert_to_dynamodb_format(data):
    """Convert Python types to DynamoDB compatible types."""
    if isinstance(data, float):
        return Decimal(str(data))
    elif isinstance(data, dict):
        return {k: convert_to_dynamodb_format(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_to_dynamodb_format(i) for i in data]
    return data


async def scrape_and_store(brand: str, query: str, table) -> dict:
    """Scrape product data and store in DynamoDB."""
    print(f"  Scraping: {brand} {query}...", end=" ", flush=True)

    try:
        # Scrape from Danawa
        offers = await search_danawa(query, brand, max_results=10)

        if not offers:
            print("No results")
            return {"brand": brand, "query": query, "status": "no_results", "count": 0}

        # Prepare data for DynamoDB
        now = datetime.now(timezone.utc)
        ttl_timestamp = int(now.timestamp()) + (TTL_HOURS * 3600)

        # Convert offers to dict
        offers_data = []
        for offer in offers:
            offer_dict = {
                "source": offer.source,
                "title": offer.title,
                "url": offer.url,
                "price_krw": offer.price_krw,
                "rating": float(offer.rating) if offer.rating else None,
                "review_count": offer.review_count,
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
            item["best_rating"] = convert_to_dynamodb_format(best.rating)

        # Store in DynamoDB
        table.put_item(Item=item)

        print(f"OK ({len(offers)} offers, best: {item.get('best_price', 'N/A')}원)")
        return {"brand": brand, "query": query, "status": "success", "count": len(offers)}

    except Exception as e:
        print(f"Error: {e}")
        return {"brand": brand, "query": query, "status": "error", "error": str(e)}


async def run_scraper(products: list, table):
    """Run scraper for all products."""
    print(f"\n{'='*50}")
    print(f"Starting scrape at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*50}\n")

    results = []
    for product in products:
        result = await scrape_and_store(product["brand"], product["query"], table)
        results.append(result)
        # Small delay between requests
        await asyncio.sleep(1)

    # Summary
    success = sum(1 for r in results if r["status"] == "success")
    total = len(results)
    print(f"\n{'='*50}")
    print(f"Completed: {success}/{total} products scraped successfully")
    print(f"{'='*50}\n")

    return results


def main():
    parser = argparse.ArgumentParser(description="Local Danawa scraper with DynamoDB storage")
    parser.add_argument("--query", type=str, help="Specific product query to scrape")
    parser.add_argument("--brand", type=str, default="농심", help="Brand name (default: 농심)")
    parser.add_argument("--loop", type=int, help="Run continuously every N minutes")
    parser.add_argument("--list", action="store_true", help="List current data in DynamoDB")
    args = parser.parse_args()

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
        print("Press Ctrl+C to stop\n")
        try:
            while True:
                asyncio.run(run_scraper(products, table))
                print(f"Next run in {args.loop} minutes...")
                time.sleep(args.loop * 60)
        except KeyboardInterrupt:
            print("\nStopped by user")
    else:
        asyncio.run(run_scraper(products, table))


if __name__ == "__main__":
    main()
