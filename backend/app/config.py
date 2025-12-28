"""Configuration management using environment variables - 다나와 스크래핑 전용."""
import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class Settings:
    """Application settings loaded from environment variables."""

    # AWS Bedrock (LLM 요약용, 옵션)
    aws_region: str = "ap-northeast-2"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    bedrock_model_id: str = "amazon.titan-text-express-v1"

    # Cache settings
    cache_ttl_seconds: int = 900  # 15 minutes
    rate_limit_seconds: int = 60  # 1 minute between force refreshes

    # Server settings
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    debug: bool = False

    def __post_init__(self):
        """Load from environment variables."""
        self.aws_region = os.getenv("AWS_REGION", "ap-northeast-2")
        self.aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
        self.aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        self.bedrock_model_id = os.getenv("BEDROCK_MODEL_ID", "amazon.titan-text-express-v1")
        self.cache_ttl_seconds = int(os.getenv("CACHE_TTL_SECONDS", "900"))
        self.rate_limit_seconds = int(os.getenv("RATE_LIMIT_SECONDS", "60"))
        self.backend_host = os.getenv("BACKEND_HOST", "0.0.0.0")
        self.backend_port = int(os.getenv("BACKEND_PORT", "8000"))
        self.debug = os.getenv("DEBUG", "false").lower() == "true"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
