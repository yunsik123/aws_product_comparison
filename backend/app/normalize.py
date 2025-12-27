"""Product name normalization and matching."""
import re
from typing import List, Tuple, Optional
from dataclasses import dataclass

try:
    from rapidfuzz import fuzz
except ImportError:
    # Fallback if rapidfuzz not installed
    fuzz = None

from .schemas import Offer
from .utils import clean_product_name


@dataclass
class MatchScore:
    """Score result for product matching."""
    offer: Offer
    score: float
    reasons: List[str]


def normalize_product_name(name: str) -> str:
    """Normalize product name for comparison.
    
    Removes common patterns and normalizes spacing.
    """
    # Convert to lowercase for comparison
    name = name.lower()
    
    # Remove brand variations
    brand_patterns = [
        r'\b농심\b', r'\b오뚜기\b', r'\b삼양\b', r'\b팔도\b',
        r'\bnongshim\b', r'\bottogi\b', r'\bsamyang\b', r'\bpaldo\b'
    ]
    for pattern in brand_patterns:
        name = re.sub(pattern, '', name, flags=re.IGNORECASE)
    
    # Use the utility function for cleaning
    name = clean_product_name(name)
    
    # Additional normalization
    name = name.lower()
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name


def calculate_match_score(
    query: str,
    brand: str,
    offer: Offer
) -> MatchScore:
    """Calculate how well an offer matches the search query.
    
    Args:
        query: Original search query
        brand: Expected brand name
        offer: Offer to score
        
    Returns:
        MatchScore with score (0-100) and reasons
    """
    score = 0.0
    reasons = []
    
    title = offer.title
    normalized_query = normalize_product_name(query)
    normalized_title = normalize_product_name(title)
    
    # 1. String similarity (up to 50 points)
    if fuzz:
        ratio = fuzz.ratio(normalized_query, normalized_title)
        partial_ratio = fuzz.partial_ratio(normalized_query, normalized_title)
        # Use the better of the two
        similarity = max(ratio, partial_ratio)
        score += similarity * 0.5
        reasons.append(f"String similarity: {similarity:.1f}%")
    else:
        # Simple fallback: check if query words are in title
        query_words = set(normalized_query.split())
        title_words = set(normalized_title.split())
        if query_words:
            overlap = len(query_words & title_words) / len(query_words)
            score += overlap * 50
            reasons.append(f"Word overlap: {overlap*100:.1f}%")
    
    # 2. Brand match (up to 20 points)
    brand_lower = brand.lower()
    title_lower = title.lower()
    if brand_lower in title_lower:
        score += 20
        reasons.append(f"Brand '{brand}' found in title")
    
    # 3. Has price (5 points)
    if offer.price_krw:
        score += 5
        reasons.append("Has price")
    
    # 4. Has rating (5 points)
    if offer.rating is not None:
        score += 5
        reasons.append("Has rating")
    
    # 5. Has reviews (10 points)
    if offer.review_count and offer.review_count > 0:
        score += 10
        reasons.append(f"Has {offer.review_count} reviews")
    
    # 6. Has image (5 points)
    if offer.image_url:
        score += 5
        reasons.append("Has image")
    
    # 7. Penalty for likely wrong products
    wrong_keywords = ['세트', '박스', '묶음', '대용량', '업소용']
    if any(kw in title_lower for kw in wrong_keywords):
        if '세트' not in query.lower() and '박스' not in query.lower():
            score -= 15
            reasons.append("Penalty: might be bulk/set product")
    
    return MatchScore(offer=offer, score=max(0, score), reasons=reasons)


def select_best_offer(
    offers: List[Offer],
    query: str,
    brand: str,
    threshold: float = 30.0
) -> Tuple[Optional[Offer], List[str]]:
    """Select the best matching offer from a list.
    
    Args:
        offers: List of offers to choose from
        query: Search query
        brand: Expected brand
        threshold: Minimum score threshold
        
    Returns:
        Tuple of (best_offer, warnings)
    """
    if not offers:
        return None, ["No offers found"]
    
    # Score all offers
    scored = [calculate_match_score(query, brand, offer) for offer in offers]
    scored.sort(key=lambda x: x.score, reverse=True)
    
    warnings = []
    best = scored[0]
    
    if best.score < threshold:
        warnings.append(
            f"Best match score ({best.score:.1f}) is below threshold ({threshold}). "
            f"Result may not be accurate."
        )
    
    # Check if there are close alternatives
    if len(scored) > 1:
        runner_up = scored[1]
        if runner_up.score > best.score * 0.9:  # Within 10%
            warnings.append(
                f"Alternative candidate: '{runner_up.offer.title}' "
                f"(score: {runner_up.score:.1f})"
            )
    
    return best.offer, warnings


def match_offers_for_product(
    offers: List[Offer],
    query: str,
    brand: str
) -> Tuple[Optional[Offer], List[Offer], List[str]]:
    """Match and rank offers for a product query.
    
    Args:
        offers: All offers from various sources
        query: Product search query
        brand: Expected brand name
        
    Returns:
        Tuple of (best_offer, all_sorted_offers, warnings)
    """
    if not offers:
        return None, [], ["No offers available"]
    
    # Score all offers
    scored = [calculate_match_score(query, brand, offer) for offer in offers]
    scored.sort(key=lambda x: x.score, reverse=True)
    
    # Get best offer and warnings
    best_offer, warnings = select_best_offer(offers, query, brand)
    
    # Return sorted offers
    sorted_offers = [s.offer for s in scored]
    
    return best_offer, sorted_offers, warnings
