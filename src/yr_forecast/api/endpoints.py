"""API endpoints for weather forecast service."""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi_cache.decorator import cache
from pydantic import ValidationError

from yr_forecast.config import (
    DEFAULT_LAT, DEFAULT_LON, DEFAULT_CITY, DEFAULT_TIMEZONE,
    CACHE_EXPIRE_SECONDS
)
from yr_forecast.weather.models import WeatherForecast
from yr_forecast.weather.service import WeatherService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/weather", tags=["weather"])


def get_weather_service() -> WeatherService:
    """Dependency to get weather service instance."""
    return WeatherService()


@router.get("/", response_model=WeatherForecast)
@cache(expire=CACHE_EXPIRE_SECONDS)
async def get_weather_forecast(
    lat: Optional[float] = Query(
        None,
        ge=-90,
        le=90,
        description="Latitude in decimal degrees (use with lon)"
    ),
    lon: Optional[float] = Query(
        None,
        ge=-180,
        le=180,
        description="Longitude in decimal degrees (use with lat)"
    ),
    city: Optional[str] = Query(
        None,
        description="City name (alternative to lat/lon, not both)"
    ),
    timezone_option: str = Query(
        "utc",
        regex="^(utc|local)$",
        description="Timezone option: 'utc' (default) or 'local' (auto-detected)"
    )
) -> WeatherForecast:
    """Get weather forecast with daily temperatures at target time.

    Args:
        lat: Latitude in decimal degrees (must provide with lon)
        lon: Longitude in decimal degrees (must provide with lat)
        city: City name as alternative to lat/lon
        timezone_option: 'utc' (default) or 'local' for auto-detected timezone

    Returns:
        WeatherForecast with daily temperature data

    Raises:
        HTTPException: If parameters are invalid or API request fails
    """
    # Validate parameters
    lat, lon, city = validate_weather_parameters(lat, lon, city)

    try:
        # Get forecast
        weather_service = get_weather_service()
        async with weather_service:
            forecast = await weather_service.get_forecast_with_geocoding(
                lat=lat,
                lon=lon,
                city=city,
                timezone_option=timezone_option
            )

        logger.info(f"Successfully retrieved forecast with {len(forecast.forecast)} days")
        return forecast

    except ValueError as e:
        logger.error(f"Error getting forecast: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except ValidationError as e:
        logger.error(f"Data validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error: data validation failed")

    except Exception as e:
        logger.error(f"Unexpected error getting forecast: {e}")
        raise HTTPException(status_code=502, detail="Weather service temporarily unavailable")

def validate_weather_parameters(
    lat: Optional[float],
    lon: Optional[float],
    city: Optional[str]
) -> tuple[float, float, str]:
    """
    Validate and normalize weather request parameters.

    Args:
        lat: Latitude in decimal degrees
        lon: Longitude in decimal degrees
        city: City name

    Returns:
        Tuple of (latitude, longitude, city)

    Raises:
        HTTPException: If validation fails
    """
    # Validate mutual exclusivity of location parameters
    has_coordinates = lat is not None or lon is not None
    has_city = city is not None

    if has_coordinates and has_city:
        raise HTTPException(
            status_code=400,
            detail="Cannot provide both coordinates and city name. Use either lat/lon OR city."
        )

    if not has_coordinates and not has_city:
        # Use default location
        lat = DEFAULT_LAT
        lon = DEFAULT_LON
        city = DEFAULT_CITY
        logger.info(f"Using default location: {city}")
    elif has_coordinates:
        # Ensure both coordinates are provided
        if lat is None or lon is None:
            raise HTTPException(
                status_code=400,
                detail="Both latitude and longitude must be provided when using coordinates."
            )

    return lat, lon, city


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