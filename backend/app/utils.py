"""Utility functions for the application."""
import re
import uuid
from datetime import datetime
from typing import Optional


def generate_request_id() -> str:
    """Generate a unique request ID."""
    return str(uuid.uuid4())


def get_current_iso_datetime() -> str:
    """Get current datetime in ISO format."""
    return datetime.now().isoformat()


def clean_product_name(name: str) -> str:
    """Clean product name for better matching.
    
    Removes common patterns like weight, count, packaging info.
    """
    # Remove weight patterns (e.g., 120g, 500ml)
    name = re.sub(r'\d+\s*(g|kg|ml|l|리터|그램|킬로그램)\b', '', name, flags=re.IGNORECASE)
    
    # Remove count patterns (e.g., 5개, 10봉, x5)
    name = re.sub(r'\d+\s*(개|봉|입|팩|박스|x)\b', '', name, flags=re.IGNORECASE)
    name = re.sub(r'x\s*\d+', '', name, flags=re.IGNORECASE)
    
    # Remove parentheses content
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'\[[^\]]*\]', '', name)
    
    # Remove extra whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def normalize_rating(rating: Optional[float], max_rating: float = 5.0) -> Optional[float]:
    """Normalize rating to 0-5 scale."""
    if rating is None:
        return None
    
    if max_rating != 5.0:
        rating = (rating / max_rating) * 5.0
    
    return round(min(max(rating, 0.0), 5.0), 2)


def safe_int(value: any) -> Optional[int]:
    """Safely convert value to integer."""
    if value is None:
        return None
    try:
        # Remove commas and convert
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        return int(float(value))
    except (ValueError, TypeError):
        return None


def safe_float(value: any) -> Optional[float]:
    """Safely convert value to float."""
    if value is None:
        return None
    try:
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        return float(value)
    except (ValueError, TypeError):
        return None
