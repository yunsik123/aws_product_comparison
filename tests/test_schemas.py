"""Tests for Pydantic schemas."""
import pytest
from datetime import datetime

from backend.app.schemas import (
    CompareRequest,
    Offer,
    ProductSummary,
    CompareResponse,
    Comparison,
    Sentiment,
    HealthResponse
)


class TestOffer:
    """Tests for Offer schema."""
    
    def test_valid_offer(self):
        """Test creating a valid offer."""
        offer = Offer(
            source="11st",
            title="농심 신라면 120g 5개",
            url="https://example.com/product",
            price_krw=4500,
            rating=4.5,
            review_count=1234,
            image_url="https://example.com/image.jpg",
            fetched_at=datetime.now().isoformat()
        )
        assert offer.source == "11st"
        assert offer.price_krw == 4500
        assert offer.rating == 4.5
    
    def test_offer_optional_fields(self):
        """Test offer with optional fields as None."""
        offer = Offer(
            source="danawa",
            title="오뚜기 진라면",
            url="https://example.com",
            fetched_at=datetime.now().isoformat()
        )
        assert offer.price_krw is None
        assert offer.rating is None
        assert offer.review_count is None
    
    def test_rating_validation(self):
        """Test rating must be between 0 and 5."""
        with pytest.raises(ValueError):
            Offer(
                source="test",
                title="Test",
                url="http://test.com",
                rating=6.0,  # Invalid
                fetched_at=datetime.now().isoformat()
            )


class TestCompareRequest:
    """Tests for CompareRequest schema."""
    
    def test_default_values(self):
        """Test default values are set correctly."""
        request = CompareRequest()
        assert request.brand_a == "농심"
        assert request.product_a == "신라면"
        assert request.brand_b == "오뚜기"
        assert request.product_b == "진라면 매운맛"
        assert request.sources == ["11st", "danawa"]
        assert request.force_refresh is False
    
    def test_custom_values(self):
        """Test custom values override defaults."""
        request = CompareRequest(
            product_a="안성탕면",
            brand_b="삼양",
            product_b="삼양라면",
            sources=["11st"],
            force_refresh=True
        )
        assert request.product_a == "안성탕면"
        assert request.brand_b == "삼양"
        assert request.force_refresh is True


class TestProductSummary:
    """Tests for ProductSummary schema."""
    
    def test_empty_summary(self):
        """Test creating empty product summary."""
        summary = ProductSummary(
            brand="농심",
            query="신라면"
        )
        assert summary.brand == "농심"
        assert summary.offers == []
        assert summary.key_features == []
        assert summary.pros == []
        assert summary.cons == []
    
    def test_summary_with_offer(self):
        """Test summary with best offer."""
        offer = Offer(
            source="11st",
            title="농심 신라면",
            url="http://test.com",
            price_krw=4500,
            fetched_at=datetime.now().isoformat()
        )
        summary = ProductSummary(
            brand="농심",
            query="신라면",
            best_offer=offer,
            offers=[offer],
            key_features=["매운맛", "봉지면"],
            pros=["저렴함"],
            cons=["나트륨 높음"]
        )
        assert summary.best_offer is not None
        assert len(summary.offers) == 1
        assert len(summary.key_features) == 2


class TestCompareResponse:
    """Tests for CompareResponse schema."""
    
    def test_valid_response(self):
        """Test creating valid compare response."""
        summary = ProductSummary(brand="농심", query="신라면")
        comparison = Comparison()
        
        response = CompareResponse(
            request_id="test-123",
            product_a=summary,
            product_b=summary,
            comparison=comparison
        )
        assert response.request_id == "test-123"
        assert response.cached is False
        assert response.warnings == []


class TestComparison:
    """Tests for Comparison schema."""
    
    def test_comparison_with_values(self):
        """Test comparison with all values."""
        comparison = Comparison(
            rating_diff=0.5,
            price_diff_krw=-500,
            review_count_diff=100
        )
        assert comparison.rating_diff == 0.5
        assert comparison.price_diff_krw == -500
    
    def test_comparison_empty(self):
        """Test comparison with no values."""
        comparison = Comparison()
        assert comparison.rating_diff is None
        assert comparison.price_diff_krw is None


class TestHealthResponse:
    """Tests for HealthResponse schema."""
    
    def test_health_response(self):
        """Test health response default values."""
        response = HealthResponse()
        assert response.status == "healthy"
        assert response.timestamp is not None
