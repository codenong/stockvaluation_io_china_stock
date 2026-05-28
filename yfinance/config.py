"""
Configuration module for the stockvaluation.io application.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
class APIConfig:
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"


# Cache Configuration
class CacheConfig:
    TYPE = os.getenv("CACHE_TYPE", "SimpleCache")
    DEFAULT_TIMEOUT = 604800 * 2  # 14 days in seconds
    THRESHOLD = 1000  # Maximum cached items
    SQLITE_PATH = "yfinance.cache"


# Rate Limiting Configuration
class RateLimitConfig:
    REQUESTS_PER_SECOND = int(os.getenv("RATE_LIMIT_REQUESTS_PER_SECOND", "2"))
    DURATION_SECONDS = int(os.getenv("RATE_LIMIT_DURATION_SECONDS", "1"))
