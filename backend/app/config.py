"""Configuration management using environment variables."""
import os
from typing import Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    elevenst_api_key: Optional[str] = None
    danawa_api_key: Optional[str] = None
    serpapi_api_key: Optional[str] = None
    
    # AWS Bedrock
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    bedrock_model_id: str = "amazon.titan-text-express-v1"
    
    # Cache settings
    cache_ttl_seconds: int = 900  # 15 minutes
    rate_limit_seconds: int = 60  # 1 minute between force refreshes
    
    # Scraping settings (default OFF)
    enable_scraping: bool = False
    
    # Server settings
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    debug: bool = False
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
