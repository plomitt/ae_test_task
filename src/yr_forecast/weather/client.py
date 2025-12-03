"""HTTP client for yr.no weather API."""

import logging
from typing import Dict, Any

import httpx
from pydantic import ValidationError

from yr_forecast.config import YR_API_BASE_URL, USER_AGENT
from yr_forecast.weather.models import YrForecastResponse

logger = logging.getLogger(__name__)


class YrWeatherClient:
    """Async client for fetching weather data from yr.no API."""

    def __init__(self, base_url: str = YR_API_BASE_URL, user_agent: str = USER_AGENT):
        """Initialize the weather client.

        Args:
            base_url: Base URL for yr.no API
            user_agent: User-Agent header for API requests
        """
        self.base_url = base_url
        self.user_agent = user_agent
        self.client = httpx.AsyncClient(
            headers={"User-Agent": self.user_agent},
            timeout=30.0
        )

    async def get_weather_forecast(self, lat: float, lon: float) -> Dict[str, Any]:
        """Fetch weather forecast for given coordinates.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees

        Returns:
            Raw forecast data from yr.no API

        Raises:
            ValueError: If coordinates are invalid
            httpx.HTTPError: If API request fails
            ValidationError: If response format is invalid
        """
        # Validate coordinates
        if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
            raise ValueError(f"Invalid coordinates: lat={lat}, lon={lon}")

        params = {"lat": round(lat, 4), "lon": round(lon, 4)}
        url = self.base_url

        logger.info(f"Fetching forecast for lat={lat}, lon={lon}")

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            # Validate response format
            try:
                YrForecastResponse(**data)
            except ValidationError as e:
                logger.error(f"Invalid API response format: {e}")
                raise ValidationError(f"Invalid API response format: {e}")

            logger.info(f"Successfully fetched forecast with {len(data.get('properties', {}).get('timeseries', []))} timeseries entries")
            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from yr.no API: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error to yr.no API: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error fetching forecast: {e}")
            raise

    async def aclose(self):
        """Close the async HTTP client."""
        await self.client.aclose()

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.aclose()