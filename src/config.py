"""
PHASE 1: Configuration
Loads environment variables and provides typed settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Supabase (optional for demo mode)
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    
    # JWT (optional for demo mode)
    jwt_secret: str = "demo-secret-change-in-production"
    
    # Rate Limiting (Cost & Abuse Control)
    # Hard limits - no grace period, no soft warnings
    rate_limit_requests_per_minute: int = 5
    rate_limit_requests_per_day: int = 50
    
    # Semantic Similarity Thresholds (Phase 7 - White Paper Enhanced)
    # STRICT Logic: False warnings acceptable, false safety NOT acceptable
    threshold_safe: float = 0.85     # >= 0.85 = SAFE (raised from 0.80)
    threshold_risky: float = 0.60    # 0.60 <= x < 0.85 = RISKY
    # < 0.60 = DANGEROUS
    
    # AI Provider (Phase 6)
    ai_provider: str = "placeholder"  # "placeholder", "openai", or "anthropic"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_embeddings_model: str = "text-embedding-3-small"
    
    # Anthropic (Claude - recommended for AI proposals)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # Gemini (Google)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # DeepSeek (OpenAI-compatible)
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"

    # Embeddings
    embeddings_provider: str = "openai"  # or "placeholder"
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    
    # Input Validation (Phase 5)
    min_text_length: int = 20
    max_text_length: int = 1800
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
