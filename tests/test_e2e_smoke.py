"""End-to-end smoke tests for the API."""
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import CompareResponse, HealthResponse


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for /health endpoint."""
    
    def test_health_check(self, client):
        """Test health check returns healthy status."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
    
    def test_health_check_v1(self, client):
        """Test health check on versioned endpoint."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestCompareEndpoint:
    """Tests for /compare endpoint."""
    
    def test_compare_default_request(self, client):
        """Test compare with default parameters."""
        response = client.post(
            "/compare",
            json={}  # Use all defaults
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate response schema
        assert "request_id" in data
        assert "product_a" in data
        assert "product_b" in data
        assert "comparison" in data
        assert "warnings" in data
        assert "cached" in data
        
        # Validate product structure
        product_a = data["product_a"]
        assert product_a["brand"] == "농심"
        assert product_a["query"] == "신라면"
        assert "offers" in product_a
        assert "key_features" in product_a
        assert "pros" in product_a
        assert "cons" in product_a
    
    def test_compare_custom_products(self, client):
        """Test compare with custom product names."""
        response = client.post(
            "/compare",
            json={
                "brand_a": "농심",
                "product_a": "안성탕면",
                "brand_b": "삼양",
                "product_b": "삼양라면",
                "sources": ["11st"]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["product_a"]["query"] == "안성탕면"
        assert data["product_b"]["brand"] == "삼양"
    
    def test_compare_validates_sources(self, client):
        """Test compare with valid sources list."""
        response = client.post(
            "/compare",
            json={
                "sources": ["11st", "danawa"]
            }
        )
        
        assert response.status_code == 200
    
    def test_compare_cached_response(self, client):
        """Test that second request returns cached response."""
        # First request
        response1 = client.post(
            "/compare",
            json={
                "product_a": "신라면",
                "product_b": "진라면 매운맛"
            }
        )
        assert response1.status_code == 200
        data1 = response1.json()
        
        # Second request (should be cached)
        response2 = client.post(
            "/compare",
            json={
                "product_a": "신라면",
                "product_b": "진라면 매운맛"
            }
        )
        assert response2.status_code == 200
        data2 = response2.json()
        
        # Second response should be cached
        assert data2["cached"] is True
    
    def test_compare_force_refresh(self, client):
        """Test force refresh bypasses cache."""
        # Make two quick requests with force_refresh
        response1 = client.post(
            "/compare",
            json={"force_refresh": True}
        )
        assert response1.status_code == 200
        
        # Second force refresh within rate limit should fail
        response2 = client.post(
            "/compare",
            json={"force_refresh": True}
        )
        # Should either succeed (if enough time passed) or return 429
        assert response2.status_code in [200, 429]
    
    def test_compare_response_schema(self, client):
        """Test response matches CompareResponse schema."""
        response = client.post("/compare", json={})
        
        assert response.status_code == 200
        
        # Validate with Pydantic model
        data = response.json()
        compare_response = CompareResponse.model_validate(data)
        
        assert compare_response.request_id is not None
        assert compare_response.product_a is not None
        assert compare_response.product_b is not None


class TestComparisonMetrics:
    """Tests for comparison calculation."""
    
    def test_comparison_has_metrics(self, client):
        """Test comparison includes diff metrics."""
        response = client.post("/compare", json={})
        
        assert response.status_code == 200
        data = response.json()
        
        comparison = data["comparison"]
        # These may be None if data not available
        assert "rating_diff" in comparison
        assert "price_diff_krw" in comparison
        assert "review_count_diff" in comparison


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_invalid_source(self, client):
        """Test handling of invalid source."""
        response = client.post(
            "/compare",
            json={"sources": ["invalid_source"]}
        )
        
        # Should still succeed but with warnings
        assert response.status_code == 200
        data = response.json()
        assert len(data["warnings"]) > 0
