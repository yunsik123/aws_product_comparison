"""HTML scraping fallback connector (default OFF).

WARNING: This connector is disabled by default.
Only enable via ENABLE_SCRAPING=true environment variable.
Always respect robots.txt and terms of service.
"""
import httpx
from typing import List, Optional

from ..schemas import Offer
from ..config import get_settings
from ..utils import get_current_iso_datetime


async def search_scrape_fallback(
    query: str,
    brand: Optional[str] = None,
    max_results: int = 10
) -> List[Offer]:
    """Search products using HTML scraping (DISABLED BY DEFAULT).
    
    This is a fallback method when APIs are unavailable.
    Only works when ENABLE_SCRAPING=true in environment.
    
    Args:
        query: Search query (product name)
        brand: Brand name to include in search
        max_results: Maximum number of results to return
        
    Returns:
        List of Offer objects (empty if disabled)
    """
    settings = get_settings()
    
    # Check if scraping is explicitly enabled
    if not settings.enable_scraping:
        print("Scraping is disabled. Set ENABLE_SCRAPING=true to enable.")
        return []
    
    # This is a placeholder - actual scraping would require:
    # 1. Checking robots.txt
    # 2. Respecting rate limits
    # 3. Using proper User-Agent
    # 4. Implementing exponential backoff
    
    # For safety, return empty list
    # Implement specific scraping logic only if absolutely necessary
    # and after reviewing target site's terms of service
    
    return []


async def _check_robots_txt(domain: str) -> bool:
    """Check if scraping is allowed by robots.txt."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"https://{domain}/robots.txt")
            # Basic check - would need proper parsing for production
            if response.status_code == 200:
                text = response.text.lower()
                # Check for general disallow
                if "disallow: /" in text and "user-agent: *" in text:
                    return False
            return True
    except Exception:
        return False
