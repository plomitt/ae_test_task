"""Weather service for processing forecast data."""

import logging
import zoneinfo
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

import httpx
from pydantic import ValidationError

from yr_forecast.config import (
    DEFAULT_LAT, DEFAULT_LON, DEFAULT_TIMEZONE,
    TARGET_HOUR, TIME_TOLERANCE_HOURS
)
from yr_forecast.weather.client import YrWeatherClient
from yr_forecast.weather.geocoding import GeocodingService, GeocodingError
from yr_forecast.weather.models import (
    LocationInfo, DailyTemperature, WeatherForecast,
    YrForecastResponse
)

logger = logging.getLogger(__name__)


class WeatherService:
    """Service for processing weather forecast data."""

    def __init__(
        self,
        client: Optional[YrWeatherClient] = None,
        geocoding_service: Optional[GeocodingService] = None
    ):
        """Initialize the weather service.

        Args:
            client: Weather client instance (creates default if None)
            geocoding_service: Geocoding service instance (creates default if None)
        """
        self.client = client or YrWeatherClient()
        self.geocoding_service = geocoding_service or GeocodingService()

    async def get_forecast_with_geocoding(
        self,
        lat: float,
        lon: float,
        city: Optional[str] = None,
        timezone_option: str = "utc"
    ) -> WeatherForecast:
        """
        Get weather forecast with automatic geocoding and timezone detection.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            city: Optional city name
            timezone_option: 'utc' or 'local' for auto-detected timezone

        Returns:
            WeatherForecast with daily temperatures

        Raises:
            GeocodingError: If geocoding fails
            ValueError: If coordinates are invalid
            httpx.HTTPError: If API request fails
            ValidationError: If response format is invalid
        """
        try:
            # Resolve location and timezone
            if city:
                # Geocode city to get coordinates
                logger.info(f"Geocoding city: {city}")
                resolved_lat, resolved_lon, resolved_city = self.geocoding_service.resolve_location(city=city)
            else:
                # Use provided coordinates and reverse geocode for city name
                resolved_lat = lat
                resolved_lon = lon
                resolved_city = self.geocoding_service.reverse_geocode(lat, lon) or city or "Unknown Location"

            # Determine timezone
            if timezone_option == "local":
                timezone = self.geocoding_service.get_timezone(resolved_lat, resolved_lon)
                logger.info(f"Using auto-detected timezone: {timezone}")
            else:
                timezone = "UTC"
                logger.info("Using UTC timezone")

            logger.info(f"Getting forecast for lat={resolved_lat}, lon={resolved_lon}, city={resolved_city}, timezone={timezone}")

            # Get weather forecast
            return await self.get_daily_temperatures(
                lat=resolved_lat,
                lon=resolved_lon,
                city=resolved_city,
                timezone_str=timezone
            )

        except GeocodingError as e:
            logger.error(f"Geocoding error: {e}")
            raise

    async def get_daily_temperatures(
        self,
        lat: float = DEFAULT_LAT,
        lon: float = DEFAULT_LON,
        city: Optional[str] = None,
        timezone_str: str = DEFAULT_TIMEZONE
    ) -> WeatherForecast:
        """Get daily temperatures at target time.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees
            city: Optional city name
            timezone_str: Timezone identifier

        Returns:
            WeatherForecast with daily temperatures

        Raises:
            ValueError: If coordinates are invalid
            httpx.HTTPError: If API request fails
            ValidationError: If response format is invalid
        """
        try:
            # Fetch raw forecast data
            raw_data = await self.client.get_weather_forecast(lat, lon)

            # Process timeseries data to get daily temperatures at target time
            daily_temps = self._process_timeseries_data(raw_data, timezone_str)

            # Create location info
            location = LocationInfo(
                lat=lat,
                lon=lon,
                city=city or 'Unkown location',
                timezone=timezone_str
            )

            return WeatherForecast(
                location=location,
                timezone=timezone_str,
                forecast=daily_temps
            )

        except (ValueError, httpx.HTTPError, ValidationError) as e:
            logger.error(f"Error getting weather forecast in get_daily_temperatures: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting weather forecast in get_daily_temperatures: {e}")
            raise

    def _process_timeseries_data(
        self,
        raw_data: Dict,
        timezone_str: str
    ) -> List[DailyTemperature]:
        """Process raw timeseries data to extract daily temperatures.

        Args:
            raw_data: Raw API response from yr.no
            timezone_str: Target timezone for local time conversion

        Returns:
            List of daily temperature forecasts
        """
        try:
            # Validate and parse response
            forecast_response = YrForecastResponse(**raw_data)
            timeseries = forecast_response.properties.get('timeseries', [])

            if not timeseries:
                raise ValueError("No timeseries data in forecast response")

            logger.info(f"Processing {len(timeseries)} timeseries entries")

            # Enrich timeseries with pre-calculated timestamps
            enriched_timeseries = self._enrich_timeseries_with_timestamps(timeseries, timezone_str)

            # Group enriched timeseries by date
            daily_data = self._group_by_date(enriched_timeseries)

            # Extract temperature closest to target time for each day
            daily_temps = self._extract_daily_temperatures(daily_data, timezone_str)
            return daily_temps

        except ValidationError as e:
            logger.error(f"Invalid forecast data format: {e}")
            raise ValueError(f"Invalid forecast data format: {e}")

    def _enrich_timeseries_with_timestamps(self, timeseries: List[Dict], timezone_str: str) -> List[Dict]:
        """Enrich timeseries entries with pre-calculated timestamps.

        Args:
            timeseries: List of raw timeseries entries
            timezone_str: Target timezone for local time conversion

        Returns:
            List of enriched entries with 'utc_time' and 'local_time' fields added
        """
        enriched_timeseries = []
        for entry in timeseries:
            try:
                utc_time, local_time = self._parse_timestamp(entry['time'], timezone_str)

                # Enrich with timestamps
                enriched_entry = entry.copy()
                enriched_entry['utc_time'] = utc_time
                enriched_entry['local_time'] = local_time
                enriched_timeseries.append(enriched_entry)

            except (KeyError, ValueError, OSError) as e:
                logger.warning(f"Skipping invalid timeseries entry during enrichment: {e}")
                continue

        return enriched_timeseries
    
    def _parse_timestamp(self, timestamp_str: str, timezone_str: str) -> tuple:
        """Parse UTC timestamp and convert to local timezone.

        Args:
            timestamp_str: ISO timestamp string ending in 'Z'
            timezone_str: Target timezone identifier

        Returns:
            Tuple of (utc_time, local_time)
        """
        utc_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        local_time = utc_time.astimezone(zoneinfo.ZoneInfo(timezone_str))
        return utc_time, local_time

    def _group_by_date(
        self,
        timeseries: List[Dict]
    ) -> Dict[str, List[Dict]]:
        """Group timeseries entries by local date.

        Args:
            timeseries: List of timeseries entries
            timezone_str: Target timezone

        Returns:
            Dictionary mapping dates to timeseries entries
        """
        daily_data = defaultdict(list)

        for entry in timeseries:
            try:
                local_time = entry['local_time']

                # Group by local date
                local_date = local_time.strftime('%Y-%m-%d')
                daily_data[local_date].append(entry)

            except (KeyError, ValueError, OSError) as e:
                logger.warning(f"Skipping invalid timeseries entry: {e}")
                continue

        return dict(daily_data)
    
    def _extract_daily_temperatures(self, daily_data: Dict[str, List[Dict]], timezone_str: str) -> List[DailyTemperature]:
        """Extract temperature closest to target time for each day.

        Args:
            daily_data: Dictionary mapping dates to lists of timeseries entries
            timezone_str: Target timezone (needed for _find_closest_to_target_hour)

        Returns:
            List of daily temperature forecasts
        """
        daily_temps = []
        for date, entries in sorted(daily_data.items()):
            temp = self._find_closest_to_target_hour(entries, timezone_str)
            if temp:
                daily_temps.append(temp)

        logger.info(f"Extracted {len(daily_temps)} daily temperature forecasts")
        return daily_temps

    def _find_closest_to_target_hour(
        self,
        daily_entries: List[Dict],
        timezone_str: str
    ) -> Optional[DailyTemperature]:
        """Find entry closest to target hour for a given day.

        Args:
            daily_entries: Timeseries entries for one day
            timezone_str: Target timezone

        Returns:
            DailyTemperature for closest time to target, or None
        """
        if not daily_entries:
            return None

        target_time = timedelta(hours=TARGET_HOUR)
        best_entry = None
        min_diff = timedelta.max

        for entry in daily_entries:
            try:
                local_time = entry['local_time']

                # Calculate difference from target hour
                local_hour = local_time.hour
                local_minute = local_time.minute
                current_time = timedelta(hours=local_hour, minutes=local_minute)

                diff = abs(current_time - target_time)

                # Only consider entries within tolerance
                if diff <= timedelta(hours=TIME_TOLERANCE_HOURS) and diff < min_diff:
                    min_diff = diff
                    best_entry = entry

            except (KeyError, ValueError, OSError) as e:
                logger.warning(f"Error processing entry: {e}")
                continue

        if best_entry:
            return self._create_daily_temperature(best_entry)

        return None

    def _create_daily_temperature(
        self,
        entry: Dict
    ) -> DailyTemperature:
        """Create DailyTemperature from timeseries entry.

        Args:
            entry: Timeseries entry
            timezone_str: Target timezone

        Returns:
            DailyTemperature object
        """
        try:
            local_time = entry['local_time']

            # Extract temperature
            temperature = entry['data']['instant']['details']['air_temperature']

            return DailyTemperature(
                date=local_time.strftime('%Y-%m-%d'),
                time=local_time.strftime('%H:%M'),
                temperature_c=temperature
            )

        except (KeyError, ValueError, OSError) as e:
            logger.error(f"Error creating daily temperature: {e}")
            raise ValueError(f"Error creating daily temperature: {e}")

    async def aclose(self):
        """Close the weather client."""
        if self.client:
            try:
                await self.client.aclose()
            except Exception as e:
                logger.error(f"Error closing weather client: {e}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        try:
            await self.aclose()
        except Exception as e:
            logger.error(f"Error during weather service cleanup in __aexit__: {e}")