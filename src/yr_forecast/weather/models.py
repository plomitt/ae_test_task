"""Data models for weather forecast service."""

from typing import List, Optional

from pydantic import BaseModel, Field


class LocationInfo(BaseModel):
    """Location information model."""
    lat: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    city: Optional[str] = Field(None, description="City name if known")
    timezone: str = Field(..., description="Timezone identifier")


class DailyTemperature(BaseModel):
    """Daily temperature forecast model."""
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    time: str = Field(..., description="Time in HH:MM format")
    temperature_c: float = Field(..., description="Temperature in Celsius")


class WeatherForecast(BaseModel):
    """Weather forecast response model."""
    location: LocationInfo = Field(..., description="Location information")
    timezone: str = Field(..., description="Timezone of the forecast")
    forecast: List[DailyTemperature] = Field(..., description="Daily temperature forecasts")


class YrTimeseriesEntry(BaseModel):
    """Raw timeseries entry from yr.no API."""
    time: str = Field(..., description="ISO timestamp")
    data: dict = Field(..., description="Weather data")


class YrForecastResponse(BaseModel):
    """Raw response from yr.no Locationforecast API."""
    type: str = Field(..., description="GeoJSON type")
    geometry: dict = Field(..., description="Location geometry")
    properties: dict = Field(..., description="Forecast properties")


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Additional error details")