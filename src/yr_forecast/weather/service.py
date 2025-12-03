"""Weather service for processing forecast data."""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

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

    def get_daily_temperatures(
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
        # Fetch raw forecast data
        raw_data = self.client.get_weather_forecast(lat, lon)

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

            # Group timeseries by date
            daily_data = self._group_by_date(timeseries, timezone_str)

            # Extract temperature closest to target time for each day
            daily_temps = []
            for date, entries in sorted(daily_data.items()):
                temp = self._find_closest_to_target_hour(entries, timezone_str)
                if temp:
                    daily_temps.append(temp)

            logger.info(f"Extracted {len(daily_temps)} daily temperature forecasts")
            return daily_temps

        except ValidationError as e:
            logger.error(f"Invalid forecast data format: {e}")
            raise ValueError(f"Invalid forecast data format: {e}")

    def _group_by_date(
        self,
        timeseries: List[Dict],
        timezone_str: str
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
                # Parse UTC timestamp
                utc_time = datetime.fromisoformat(entry['time'].replace('Z', '+00:00'))

                # Convert to local timezone
                import zoneinfo
                tz = zoneinfo.ZoneInfo(timezone_str)
                local_time = utc_time.astimezone(tz)

                # Group by local date
                local_date = local_time.strftime('%Y-%m-%d')
                daily_data[local_date].append(entry)

            except (KeyError, ValueError, OSError) as e:
                logger.warning(f"Skipping invalid timeseries entry: {e}")
                continue

        return dict(daily_data)

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
                # Parse and convert timestamp
                utc_time = datetime.fromisoformat(entry['time'].replace('Z', '+00:00'))
                import zoneinfo
                tz = zoneinfo.ZoneInfo(timezone_str)
                local_time = utc_time.astimezone(tz)

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
            return self._create_daily_temperature(best_entry, timezone_str)

        return None

    def _create_daily_temperature(
        self,
        entry: Dict,
        timezone_str: str
    ) -> DailyTemperature:
        """Create DailyTemperature from timeseries entry.

        Args:
            entry: Timeseries entry
            timezone_str: Target timezone

        Returns:
            DailyTemperature object
        """
        try:
            # Parse and convert timestamp
            utc_time = datetime.fromisoformat(entry['time'].replace('Z', '+00:00'))
            import zoneinfo
            tz = zoneinfo.ZoneInfo(timezone_str)
            local_time = utc_time.astimezone(tz)

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

    def close(self):
        """Close the weather client."""
        if self.client:
            self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()