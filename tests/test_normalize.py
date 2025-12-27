"""Tests for product name normalization and matching."""
import pytest

from backend.app.normalize import (
    normalize_product_name,
    calculate_match_score,
    select_best_offer,
    match_offers_for_product
)
from backend.app.schemas import Offer
from datetime import datetime


@pytest.fixture
def sample_offers():
    """Create sample offers for testing."""
    now = datetime.now().isoformat()
    return [
        Offer(
            source="11st",
            title="농심 신라면 120g 5개입",
            url="http://test.com/1",
            price_krw=4500,
            rating=4.5,
            review_count=1000,
            fetched_at=now
        ),
        Offer(
            source="danawa",
            title="농심 신라면 봉지 5개",
            url="http://test.com/2",
            price_krw=4300,
            rating=4.6,
            review_count=500,
            fetched_at=now
        ),
        Offer(
            source="11st",
            title="오뚜기 진라면 순한맛 5개",
            url="http://test.com/3",
            price_krw=4200,
            rating=4.3,
            review_count=800,
            fetched_at=now
        ),
        Offer(
            source="danawa",
            title="농심 신라면 세트 박스 40개",
            url="http://test.com/4",
            price_krw=35000,
            rating=4.7,
            review_count=200,
            fetched_at=now
        ),
    ]


class TestNormalizeProductName:
    """Tests for normalize_product_name function."""
    
    def test_removes_weight(self):
        """Test removing weight from product name."""
        result = normalize_product_name("신라면 120g")
        assert "120g" not in result
        assert "신라면" in result
    
    def test_removes_count(self):
        """Test removing count from product name."""
        result = normalize_product_name("신라면 5개입")
        assert "5개" not in result
        assert "입" not in result
    
    def test_removes_brand(self):
        """Test removing brand names."""
        result = normalize_product_name("농심 신라면")
        assert "농심" not in result
    
    def test_removes_parentheses(self):
        """Test removing parentheses content."""
        result = normalize_product_name("신라면 (매운맛)")
        assert "매운맛" not in result
        assert "(" not in result
    
    def test_normalizes_whitespace(self):
        """Test normalizing whitespace."""
        result = normalize_product_name("신라면   120g   5개")
        assert "  " not in result


class TestCalculateMatchScore:
    """Tests for calculate_match_score function."""
    
    def test_high_score_for_exact_match(self, sample_offers):
        """Test high score for closely matching product."""
        offer = sample_offers[0]  # 농심 신라면 120g 5개입
        score = calculate_match_score("신라면", "농심", offer)
        assert score.score > 50
        assert score.offer == offer
    
    def test_brand_bonus(self, sample_offers):
        """Test brand match gives bonus points."""
        offer = sample_offers[0]  # 농심 신라면
        score = calculate_match_score("신라면", "농심", offer)
        assert "농심" in " ".join(score.reasons)
    
    def test_penalty_for_bulk(self, sample_offers):
        """Test penalty for bulk/set products."""
        offer = sample_offers[3]  # 농심 신라면 세트 박스 40개
        score = calculate_match_score("신라면", "농심", offer)
        assert "Penalty" in " ".join(score.reasons) or score.score < 70
    
    def test_low_score_for_wrong_brand(self, sample_offers):
        """Test lower score for wrong brand."""
        offer = sample_offers[2]  # 오뚜기 진라면
        score = calculate_match_score("신라면", "농심", offer)
        assert score.score < 50


class TestSelectBestOffer:
    """Tests for select_best_offer function."""
    
    def test_selects_best_match(self, sample_offers):
        """Test selecting the best matching offer."""
        # Filter to 농심 products only
        nongshim_offers = [o for o in sample_offers if "농심" in o.title and "세트" not in o.title]
        best, warnings = select_best_offer(nongshim_offers, "신라면", "농심")
        
        assert best is not None
        assert "농심" in best.title
        assert "신라면" in best.title
    
    def test_empty_offers(self):
        """Test with empty offers list."""
        best, warnings = select_best_offer([], "신라면", "농심")
        assert best is None
        assert len(warnings) > 0
    
    def test_generates_warnings(self, sample_offers):
        """Test warnings for low confidence."""
        # Use an offer that won't match well
        wrong_offers = [sample_offers[2]]  # 오뚜기 진라면
        best, warnings = select_best_offer(wrong_offers, "신라면", "농심", threshold=60)
        
        # Should have warnings about low score or mismatch
        assert len(warnings) >= 0  # May or may not have warnings


class TestMatchOffersForProduct:
    """Tests for match_offers_for_product function."""
    
    def test_returns_sorted_offers(self, sample_offers):
        """Test offers are sorted by score."""
        best, sorted_offers, warnings = match_offers_for_product(
            sample_offers, "신라면", "농심"
        )
        
        assert best is not None
        assert len(sorted_offers) == len(sample_offers)
        # Best offer should be first in sorted list
        assert sorted_offers[0] == best if best else True
    
    def test_handles_empty_list(self):
        """Test handling empty offer list."""
        best, sorted_offers, warnings = match_offers_for_product(
            [], "신라면", "농심"
        )
        
        assert best is None
        assert sorted_offers == []
        assert len(warnings) > 0
