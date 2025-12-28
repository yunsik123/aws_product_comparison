"""Pydantic schemas for the product comparison API."""
from typing import List, Optional, Literal, Dict
from pydantic import BaseModel, Field
from datetime import datetime


class CompareRequest(BaseModel):
    """Request schema for product comparison."""
    brand_a: str = Field(default="농심", description="Brand A name")
    product_a: str = Field(default="신라면", description="Product A name")
    brand_b: str = Field(default="오뚜기", description="Brand B name")
    product_b: str = Field(default="진라면 매운맛", description="Product B name")
    sources: List[Literal["danawa"]] = Field(
        default=["danawa"],
        description="Data sources to use (danawa only)"
    )
    force_refresh: bool = Field(default=False, description="Force refresh bypassing cache")


class Offer(BaseModel):
    """Single product offer from a source."""
    source: str = Field(..., description="Data source name")
    title: str = Field(..., description="Product title")
    url: str = Field(..., description="Product URL")
    price_krw: Optional[int] = Field(None, description="Price in KRW")
    rating: Optional[float] = Field(None, ge=0, le=5, description="Rating (0-5 scale)")
    review_count: Optional[int] = Field(None, ge=0, description="Number of reviews")
    image_url: Optional[str] = Field(None, description="Product image URL")
    fetched_at: str = Field(..., description="ISO datetime when data was fetched")


class Sentiment(BaseModel):
    """Sentiment analysis result."""
    positive_pct: float = Field(0.0, ge=0, le=100)
    negative_pct: float = Field(0.0, ge=0, le=100)
    neutral_pct: float = Field(0.0, ge=0, le=100)


class ProductSummary(BaseModel):
    """Aggregated product summary."""
    brand: str = Field(..., description="Brand name")
    query: str = Field(..., description="Search query used")
    best_offer: Optional[Offer] = Field(None, description="Best matching offer")
    offers: List[Offer] = Field(default_factory=list, description="All offers from sources")
    key_features: List[str] = Field(default_factory=list, description="Key features (evidence-based)")
    pros: List[str] = Field(default_factory=list, description="Pros (evidence-based)")
    cons: List[str] = Field(default_factory=list, description="Cons (evidence-based)")
    sentiment: Optional[Sentiment] = Field(None, description="Sentiment analysis")
    evidence: List[str] = Field(default_factory=list, description="Evidence sentences")


class Comparison(BaseModel):
    """Comparison metrics between two products."""
    rating_diff: Optional[float] = Field(None, description="Rating difference (A - B)")
    price_diff_krw: Optional[int] = Field(None, description="Price difference in KRW (A - B)")
    review_count_diff: Optional[int] = Field(None, description="Review count difference (A - B)")


class CompareResponse(BaseModel):
    """Response schema for product comparison."""
    request_id: str = Field(..., description="Unique request identifier")
    product_a: ProductSummary = Field(..., description="Product A summary")
    product_b: ProductSummary = Field(..., description="Product B summary")
    comparison: Comparison = Field(..., description="Comparison metrics")
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    cached: bool = Field(default=False, description="Whether result was cached")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(default="healthy")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
