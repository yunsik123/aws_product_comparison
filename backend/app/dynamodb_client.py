"""DynamoDB client for reading cached product data."""
import os
from typing import List, Optional, Tuple
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from .schemas import Offer
from .config import get_settings


DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "nongshim-product-cache")


def get_dynamodb_table():
    """Get DynamoDB table resource."""
    settings = get_settings()
    dynamodb = boto3.resource('dynamodb', region_name=settings.aws_region)
    return dynamodb.Table(DYNAMODB_TABLE)


def decimal_to_float(obj):
    """Convert Decimal to float for JSON serialization."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    return obj


async def get_cached_offers(brand: str, query: str) -> Tuple[List[Offer], bool]:
    """
    Get cached product offers from DynamoDB.

    Args:
        brand: Brand name (e.g., "농심")
        query: Product query (e.g., "신라면")

    Returns:
        Tuple of (list of Offers, is_from_cache)
    """
    try:
        table = get_dynamodb_table()

        # Query DynamoDB
        response = table.get_item(
            Key={
                "pk": f"PRODUCT#{brand}",
                "sk": f"QUERY#{query}"
            }
        )

        item = response.get('Item')
        if not item:
            return [], False

        # Convert stored offers back to Offer objects
        offers_data = decimal_to_float(item.get('offers', []))
        offers = []

        for offer_dict in offers_data:
            offer = Offer(
                source=offer_dict.get('source', 'danawa'),
                title=offer_dict.get('title', ''),
                url=offer_dict.get('url', ''),
                price_krw=offer_dict.get('price_krw'),
                rating=offer_dict.get('rating'),
                review_count=offer_dict.get('review_count'),
                image_url=offer_dict.get('image_url'),
                fetched_at=offer_dict.get('fetched_at', item.get('updated_at', ''))
            )
            offers.append(offer)

        return offers, True

    except ClientError as e:
        print(f"DynamoDB error: {e}")
        return [], False
    except Exception as e:
        print(f"Error getting cached offers: {e}")
        return [], False


async def get_all_cached_products() -> List[dict]:
    """Get all cached products from DynamoDB."""
    try:
        table = get_dynamodb_table()
        response = table.scan()
        items = response.get('Items', [])
        return [decimal_to_float(item) for item in items]
    except Exception as e:
        print(f"Error scanning DynamoDB: {e}")
        return []
