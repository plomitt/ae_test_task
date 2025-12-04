"""Configuration settings for the weather forecast service."""

import os
from typing import Final
from dotenv import load_dotenv

load_dotenv()

# API Configuration
YR_API_BASE_URL: Final[str] = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
USER_AGENT: Final[str] = "WeatherForecastService/0.1 (user@example.com)"

# Default location (Belgrade)
DEFAULT_LAT: Final[float] = 44.8125
DEFAULT_LON: Final[float] = 20.4612
DEFAULT_CITY: Final[str] = "Belgrade"
DEFAULT_TIMEZONE: Final[str] = "Europe/Belgrade"

# Server configuration
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

# Target time settings
TARGET_HOUR: int = int(os.getenv("TARGET_HOUR", "14")) # Target time
TIME_TOLERANCE_HOURS: int = int(os.getenv("TIME_TOLERANCE_HOURS", "2"))  # Search within 2 hours of target time

# Redis cache configuration
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
CACHE_EXPIRE_SECONDS: int = int(os.getenv("CACHE_EXPIRE_SECONDS", "60"))  # 60 seconds default
CACHE_PREFIX: str = os.getenv("CACHE_PREFIX", "weather-forecast")

# Rate limiting configuration
RATE_LIMIT_REQUESTS_PER_SECOND: int = int(os.getenv("RATE_LIMIT_REQUESTS_PER_SECOND", "20"))
RATE_LIMIT_REDIS_KEY_PREFIX: str = os.getenv("RATE_LIMIT_REDIS_KEY_PREFIX", "rate_limit")
RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"