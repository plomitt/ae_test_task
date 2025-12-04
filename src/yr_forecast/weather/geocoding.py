"""Geocoding service for weather forecast."""

import logging
from functools import lru_cache
from typing import Optional, Tuple

from geopy.exc import GeocoderUnavailable, GeocoderTimedOut
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

from yr_forecast.config import GEOCODING_USER_AGENT

logger = logging.getLogger(__name__)


class GeocodingError(Exception):
    """Raised when geocoding fails."""
    pass


class GeocodingService:
    """Service for geocoding operations and timezone detection."""

    def __init__(self):
        """Initialize the geocoding service."""
        # Reuse instance for performance
        self.tf = TimezoneFinder(in_memory=True)
        self.geolocator = Nominatim(user_agent=GEOCODING_USER_AGENT)
        logger.info("GeocodingService initialized with timezonefinder and Nominatim")

    @lru_cache(maxsize=1000)
    def forward_geocode(self, city: str) -> Tuple[float, float]:
        """Convert city name to coordinates.

        Args:
            city: City name to geocode

        Returns:
            Tuple of (latitude, longitude)

        Raises:
            GeocodingError: If geocoding fails
        """
        try:
            logger.info(f"Geocoding city: {city}")
            location = self.geolocator.geocode(city)

            if not location:
                raise GeocodingError(f"City '{city}' not found")

            lat, lon = location.latitude, location.longitude
            logger.info(f"Successfully geocoded '{city}' to ({lat}, {lon})")
            return lat, lon

        except (GeocoderUnavailable, GeocoderTimedOut) as e:
            logger.error(f"Geocoding service unavailable for '{city}': {e}")
            raise GeocodingError(f"Geocoding service temporarily unavailable")
        except Exception as e:
            logger.error(f"Unexpected error geocoding '{city}': {e}")
            raise GeocodingError(f"Failed to geocode city: {e}")

    @lru_cache(maxsize=1000)
    def reverse_geocode(self, lat: float, lon: float) -> Optional[str]:
        """Convert coordinates to city name.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            City name if found, None otherwise
        """
        try:
            # Round coordinates
            lat_rounded = round(lat, 4)
            lon_rounded = round(lon, 4)

            logger.info(f"Reverse geocoding coordinates: ({lat_rounded}, {lon_rounded})")
            location = self.geolocator.reverse((lat_rounded, lon_rounded))

            if location and location.raw.get('address'):
                # Try to get city from address components
                address = location.raw['address']
                city = (
                    address.get('city') or
                    address.get('town') or
                    address.get('village') or
                    address.get('municipality') or
                    address.get('county')
                )

                if city:
                    logger.info(f"Successfully reverse geocoded ({lat_rounded}, {lon_rounded}) to '{city}'")
                    return city

            logger.info(f"No city found for coordinates ({lat_rounded}, {lon_rounded})")
            return None

        except (GeocoderUnavailable, GeocoderTimedOut) as e:
            logger.warning(f"Reverse geocoding service unavailable for ({lat}, {lon}): {e}")
            return None
        except Exception as e:
            logger.warning(f"Unexpected error reverse geocoding ({lat}, {lon}): {e}")
            return None

    def get_timezone(self, lat: float, lon: float) -> str:
        """Get timezone for coordinates.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            Timezone string (e.g., "Europe/Belgrade") or "UTC" if not found
        """
        try:
            logger.info(f"Finding timezone for coordinates: ({lat}, {lon})")
            timezone = self.tf.timezone_at(lng=lon, lat=lat)

            if timezone:
                logger.info(f"Found timezone '{timezone}' for ({lat}, {lon})")
                return timezone
            else:
                logger.warning(f"No timezone found for ({lat}, {lon}), defaulting to UTC")
                return "UTC"

        except Exception as e:
            logger.error(f"Error getting timezone for ({lat}, {lon}): {e}")
            return "UTC"

    def resolve_location(
        self,
        *,
        lat: Optional[float] = None,
        lon: Optional[float] = None,
        city: Optional[str] = None
    ) -> Tuple[float, float, str]:
        """Resolve location to coordinates and city name.

        Args:
            lat: Latitude (if coordinates provided)
            lon: Longitude (if coordinates provided)
            city: City name (if city provided)

        Returns:
            Tuple of (latitude, longitude, city_name)

        Raises:
            GeocodingError: If location resolution fails
        """
        if city:
            # Geocode city to get coordinates
            lat, lon = self.forward_geocode(city)
            resolved_city = city
        elif lat is not None and lon is not None:
            # Use provided coordinates to get city name
            resolved_city = self.reverse_geocode(lat, lon) or "Unknown Location"
        else:
            raise GeocodingError("Must provide either city name or coordinates")

        return lat, lon, resolved_city