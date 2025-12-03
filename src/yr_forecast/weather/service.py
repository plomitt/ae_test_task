"""Weather service for processing forecast data."""

import json
import logging
import os
import zoneinfo
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

import httpx
from pydantic import ValidationError

from yr_forecast.config import (
    DEFAULT_LAT, DEFAULT_LON, DEFAULT_CITY, DEFAULT_TIMEZONE,
    TARGET_HOUR, TIME_TOLERANCE_HOURS
)
from yr_forecast.weather.client import YrWeatherClient
from yr_forecast.weather.models import (
    LocationInfo, DailyTemperature, WeatherForecast,
    YrForecastResponse
)

logger = logging.getLogger(__name__)


class WeatherService:
    """Service for processing weather forecast data."""

    def __init__(self, client: Optional[YrWeatherClient] = None):
        """Initialize the weather service.

        Args:
            client: Weather client instance (creates default if None)
        """
        self.client = client or YrWeatherClient()

    def _save_debug_data(self, data, filename: str):
        """Save debug data to file with proper datetime serialization.

        Args:
            data: Data to save (dict, list, or Pydantic models)
            filename: Name of the file to save
        """
        try:
            # Create debug_data directory if it doesn't exist
            debug_dir = "debug_data"
            os.makedirs(debug_dir, exist_ok=True)

            filepath = os.path.join(debug_dir, filename)

            # Custom serializer to handle datetime objects and Pydantic models
            def json_serializer(obj):
                if hasattr(obj, 'isoformat'):  # datetime objects
                    return obj.isoformat()
                elif hasattr(obj, 'dict'):  # Pydantic models
                    return obj.dict()
                elif hasattr(obj, '__dict__'):  # Other objects
                    return obj.__dict__
                return str(obj)

            # Handle different data types
            if hasattr(data, 'dict'):  # Pydantic model
                json_data = data.dict()
            elif isinstance(data, list) and data and hasattr(data[0], 'dict'):  # List of Pydantic models
                json_data = [item.dict() for item in data]
            else:
                json_data = data

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, default=json_serializer, ensure_ascii=False)

            logger.info(f"Debug data saved to {filepath}")

        except Exception as e:
            logger.error(f"Error saving debug data to {filename}: {e}")

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
            self._save_debug_data(raw_data, "01_raw_data.json")

            # Process timeseries data to get daily temperatures at target time
            daily_temps = self._process_timeseries_data(raw_data, timezone_str)

            # Create location info
            location = LocationInfo(
                lat=lat,
                lon=lon,
                city=city or self._get_city_name(lat, lon),
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
            self._save_debug_data(enriched_timeseries, "02_enriched_timeseries.json")

            # Group enriched timeseries by date
            daily_data = self._group_by_date(enriched_timeseries)
            self._save_debug_data(daily_data, "03_daily_grouped_data.json")

            # Extract temperature closest to target time for each day
            daily_temps = self._extract_daily_temperatures(daily_data, timezone_str)
            self._save_debug_data(daily_temps, "04_daily_temperatures.json")
            return daily_temps

        except ValidationError as e:
            logger.error(f"Invalid forecast data format: {e}")
            raise ValueError(f"Invalid forecast data format: {e}")
    
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

    def _get_city_name(self, lat: float, lon: float) -> Optional[str]:
        """Get city name for known coordinates.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            City name if known, None otherwise
        """
        # Calculate if default location
        if abs(lat - DEFAULT_LAT) < 0.1 and abs(lon - DEFAULT_LON) < 0.1:
            return DEFAULT_CITY
        return None

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