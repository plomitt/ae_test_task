"""API endpoints for weather forecast service."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import ValidationError

from yr_forecast.config import DEFAULT_LAT, DEFAULT_LON, DEFAULT_CITY, DEFAULT_TIMEZONE
from yr_forecast.weather.models import WeatherForecast
from yr_forecast.weather.service import WeatherService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/weather", tags=["weather"])


def get_weather_service() -> WeatherService:
    """Dependency to get weather service instance."""
    return WeatherService()


@router.get("/", response_model=WeatherForecast)
async def get_weather_forecast(
    lat: Optional[float] = Query(
        None,
        ge=-90,
        le=90,
        description="Latitude in decimal degrees (default: Belgrade)"
    ),
    lon: Optional[float] = Query(
        None,
        ge=-180,
        le=180,
        description="Longitude in decimal degrees (default: Belgrade)"
    ),
    city: Optional[str] = Query(
        None,
        description="City name (optional, for display purposes)"
    ),
    timezone: Optional[str] = Query(
        DEFAULT_TIMEZONE,
        description="Timezone identifier (default: Europe/Belgrade)"
    ),
    weather_service: WeatherService = Depends(get_weather_service)
) -> WeatherForecast:
    """Get weather forecast with daily temperatures at target time.

    If no coordinates are provided, returns forecast for Belgrade, Serbia.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        city: Optional city name for display
        timezone: Timezone identifier for local time conversion

    Returns:
        WeatherForecast with daily temperature data

    Raises:
        HTTPException: If coordinates are invalid or API request fails
    """
    # Use default coordinates if not provided
    if lat is None:
        lat = DEFAULT_LAT
        
    if lon is None:
        lon = DEFAULT_LON

    if city is None:
        city = DEFAULT_CITY

    try:
        logger.info(f"Getting forecast for lat={lat}, lon={lon}, city={city}")

        async with weather_service:
            forecast = await weather_service.get_daily_temperatures(
                lat=lat,
                lon=lon,
                city=city,
                timezone_str=timezone
            )

        logger.info(f"Successfully retrieved forecast with {len(forecast.forecast)} days")
        return forecast

    except ValueError as e:
        logger.error(f"Invalid input: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except ValidationError as e:
        logger.error(f"Data validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error: data validation failed")

    except Exception as e:
        logger.error(f"Unexpected error getting forecast: {e}")
        raise HTTPException(status_code=502, detail="Weather service temporarily unavailable")


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint.

    Returns:
        Health status response
    """
    return {"status": "healthy", "service": "yr-forecast"}


@router.get("/info")
async def get_service_info() -> dict:
    """Get service information.

    Returns:
        Service information including default location and features
    """
    return {
        "service": "Yr.no Weather Forecast Service",
        "version": "0.1.0",
        "default_location": {
            "city": DEFAULT_CITY,
            "latitude": DEFAULT_LAT,
            "longitude": DEFAULT_LON,
            "timezone": DEFAULT_TIMEZONE
        },
        "features": [
            "Daily temperature forecasts at specific time of day",
            "Custom location support"
        ],
        "data_source": "MET Norway yr.no API"
    }