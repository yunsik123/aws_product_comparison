"""Tests for data source connectors with mock responses."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from backend.app.sources.elevenst import search_elevenst, _parse_elevenst_response
from backend.app.sources.danawa import search_danawa, _parse_danawa_response
from backend.app.sources.naver_serpapi import search_naver_serpapi, _parse_serpapi_response


# Sample 11st XML response
ELEVENST_XML_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<ProductSearchResponse>
    <Products>
        <Product>
            <ProductName>농심 신라면 120g 5개입</ProductName>
            <DetailPageUrl>https://www.11st.co.kr/products/123456</DetailPageUrl>
            <SalePrice>4500</SalePrice>
            <Rating>4.5</Rating>
            <ReviewCount>1234</ReviewCount>
            <ProductImage>https://cdn.11st.co.kr/image.jpg</ProductImage>
        </Product>
        <Product>
            <ProductName>농심 신라면 봉지 10개</ProductName>
            <DetailPageUrl>https://www.11st.co.kr/products/789012</DetailPageUrl>
            <SalePrice>8500</SalePrice>
            <Rating>4.7</Rating>
            <ReviewCount>567</ReviewCount>
            <ProductImage>https://cdn.11st.co.kr/image2.jpg</ProductImage>
        </Product>
    </Products>
</ProductSearchResponse>
"""

# Sample Danawa JSON response
DANAWA_JSON_FIXTURE = {
    "products": [
        {
            "productName": "농심 신라면 120g 5개",
            "productUrl": "https://prod.danawa.com/123",
            "minPrice": 4300,
            "rating": 4.6,
            "reviewCount": 890,
            "imageUrl": "https://img.danawa.com/image.jpg"
        },
        {
            "productName": "농심 신라면 컵 65g",
            "productUrl": "https://prod.danawa.com/456",
            "minPrice": 1200,
            "rating": 4.2,
            "reviewCount": 234,
            "imageUrl": "https://img.danawa.com/image2.jpg"
        }
    ]
}

# Sample SerpApi response
SERPAPI_JSON_FIXTURE = {
    "shopping_results": [
        {
            "title": "농심 신라면 5팩",
            "link": "https://shopping.naver.com/123",
            "price": "4,500원",
            "rating": 4.8,
            "reviews": 2345,
            "thumbnail": "https://shop-phinf.naver.net/image.jpg"
        }
    ]
}


class TestElevenstParser:
    """Tests for 11st XML response parser."""
    
    def test_parse_valid_xml(self):
        """Test parsing valid 11st XML response."""
        offers = _parse_elevenst_response(ELEVENST_XML_FIXTURE)
        
        assert len(offers) == 2
        assert offers[0].source == "11st"
        assert offers[0].title == "농심 신라면 120g 5개입"
        assert offers[0].price_krw == 4500
        assert offers[0].rating == 4.5
        assert offers[0].review_count == 1234
    
    def test_parse_empty_xml(self):
        """Test parsing empty XML."""
        offers = _parse_elevenst_response("<?xml version='1.0'?><Products></Products>")
        assert offers == []
    
    def test_parse_invalid_xml(self):
        """Test handling invalid XML."""
        offers = _parse_elevenst_response("not xml at all")
        assert offers == []


class TestDanawaParser:
    """Tests for Danawa JSON response parser."""
    
    def test_parse_valid_json(self):
        """Test parsing valid Danawa JSON response."""
        offers = _parse_danawa_response(DANAWA_JSON_FIXTURE)
        
        assert len(offers) == 2
        assert offers[0].source == "danawa"
        assert offers[0].title == "농심 신라면 120g 5개"
        assert offers[0].price_krw == 4300
        assert offers[0].rating == 4.6
    
    def test_parse_empty_json(self):
        """Test parsing empty JSON."""
        offers = _parse_danawa_response({"products": []})
        assert offers == []
    
    def test_parse_alternative_keys(self):
        """Test parsing with alternative key names."""
        data = {
            "items": [
                {
                    "name": "Test Product",
                    "url": "http://test.com",
                    "price": 1000,
                    "score": 4.0,
                    "reviews": 100,
                    "image": "http://img.com/test.jpg"
                }
            ]
        }
        offers = _parse_danawa_response(data)
        assert len(offers) == 1
        assert offers[0].title == "Test Product"


class TestSerpapiParser:
    """Tests for SerpApi response parser."""
    
    def test_parse_valid_response(self):
        """Test parsing valid SerpApi response."""
        offers = _parse_serpapi_response(SERPAPI_JSON_FIXTURE)
        
        assert len(offers) == 1
        assert offers[0].source == "naver_serpapi"
        assert offers[0].title == "농심 신라면 5팩"
        assert offers[0].price_krw == 4500
        assert offers[0].rating == 4.8
        assert offers[0].review_count == 2345
    
    def test_parse_empty_response(self):
        """Test parsing empty response."""
        offers = _parse_serpapi_response({"shopping_results": []})
        assert offers == []
    
    def test_price_parsing(self):
        """Test parsing various price formats."""
        data = {
            "shopping_results": [
                {"title": "Test", "link": "http://test.com", "price": "10,000원"},
                {"title": "Test2", "link": "http://test.com", "price": "5000"},
            ]
        }
        offers = _parse_serpapi_response(data)
        assert offers[0].price_krw == 10000
        assert offers[1].price_krw == 5000


class TestElevenstSearch:
    """Tests for 11st search function."""
    
    @pytest.mark.asyncio
    async def test_returns_empty_without_api_key(self):
        """Test returns empty list when API key not configured."""
        with patch('backend.app.sources.elevenst.get_settings') as mock_settings:
            mock_settings.return_value.elevenst_api_key = None
            
            result = await search_elevenst("신라면", "농심")
            assert result == []


class TestDanawaSearch:
    """Tests for Danawa search function."""
    
    @pytest.mark.asyncio
    async def test_returns_empty_without_api_key(self):
        """Test returns empty list when API key not configured."""
        with patch('backend.app.sources.danawa.get_settings') as mock_settings:
            mock_settings.return_value.danawa_api_key = None
            
            result = await search_danawa("신라면", "농심")
            assert result == []
