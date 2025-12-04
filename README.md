# Yr.no Weather Forecast Service

A REST API service with Web GUI that provides daily weather forecasts using MET Norway's yr.no API. The service returns temperature data for approximately 14:00 local time for as many forecast days as available, with support for both coordinates and city name geocoding.

## Features

- Daily temperature forecasts at ~14:00 (within 2 hours) local time
- Web-based GUI interface for easy access
- Geocoding support for city names
- Timezone options (UTC/Local)
- Custom location support (latitude/longitude)
- Default location: Belgrade, Serbia
- Global rate limiting to protect yr.no API (20 requests/second)
- Redis-based caching for improved performance
- Automatic API documentation (OpenAPI/Swagger)
- Input validation and error handling

## Web GUI

The service includes a clean, responsive web interface that provides an easy way to access weather forecasts without using the API directly.

### Features

- **Location Input**: Choose between entering a city name or exact coordinates
- **Timezone Options**: View forecasts in UTC or local timezone
- **Responsive Design**: Works on desktop and mobile devices
- **Real-time Results**: Get instant weather forecasts with loading indicators
- **Error Handling**: User-friendly error messages for invalid inputs

### Access

After starting the service, visit:
- **Web Interface**: http://localhost:8000/
- **API Documentation**: http://localhost:8000/docs

### Using the Web GUI

1. Open http://localhost:8000/ in your browser
2. Choose your location input method:
   - **City Name**: Enter any city name (e.g., "Paris", "Tokyo", "New York")
   - **Coordinates**: Enter latitude and longitude directly
3. Select timezone preference (UTC or Local)
4. Click "Get Weather" to see the forecast
5. View the results showing daily temperature predictions

## Quick Start

### Using Docker (Recommended)

1. **Docker compose:**
   ```bash
   docker-compose up -d
   ```

2. **Access the API:**
   - API documentation: http://localhost:8000/docs
   - Get weather: http://localhost:8000/weather/
   - Web GUI: http://localhost:8000/

### Local Development

1. **Install Poetry:**
   ```bash
   pip install poetry
   ```

2. **Install dependencies:**
   ```bash
   poetry install
   ```

3. **Run the service:**
   ```bash
   poetry run python -m yr_forecast.main
   ```
  
4. **Access the API**

## API Endpoints

### Root Endpoints

#### Web Interface
**GET** `/`

Returns the main web interface HTML page.

#### API Information
**GET** `/api`

Returns basic API information and available endpoints.

**Response:**
```json
{
  "message": "Yr.no Weather Forecast Service",
  "docs": "/docs",
  "redoc": "/redoc",
  "weather": "/weather",
  "health": "/weather/health"
}
```

### Weather API Endpoints

#### Get Weather Forecast
**GET** `/weather/`

Returns weather forecast for the specified location.

#### Parameters

- `lat` (optional): Latitude in decimal degrees (-90 to 90). Must be provided with `lon`.
- `lon` (optional): Longitude in decimal degrees (-180 to 180). Must be provided with `lat`.
- `city` (optional): City name. Alternative to lat/lon, not both.
- `timezone_option` (optional): Timezone option. Either "utc" (default) or "local" for auto-detected timezone.

#### Example Requests

```bash
# Get Belgrade forecast (default)
curl http://localhost:8000/weather/

# Get forecast by city name (with geocoding)
curl "http://localhost:8000/weather/?city=Paris&timezone_option=local"

# Get forecast by coordinates
curl "http://localhost:8000/weather/?lat=48.8575&lon=2.3514&timezone_option=utc"
```

#### Response Format

```json
{
  "location": {
    "lat": 44.8125,
    "lon": 20.4612,
    "city": "Belgrade"
  },
  "timezone": "Europe/Belgrade",
  "forecast": [
    {
      "date": "2025-12-03",
      "time": "14:00",
      "temperature_c": 9.7
    },
    {
      "date": "2025-12-04",
      "time": "14:00",
      "temperature_c": 10.0
    }
  ]
}
```

### Other Endpoints

- **GET** `/weather/health` - Service health check
- **GET** `/weather/info` - Service information and capabilities
- **GET** `/docs` - Interactive API documentation (Swagger UI)
- **GET** `/redoc` - Alternative API documentation


### Important Notes

- The service finds the temperature reading closest to 14:00 local time
- If exact 14:00 data is unavailable, it uses readings within 2 hours
- Coordinates are rounded to 4 decimal places for API efficiency
- User-Agent header is set according to yr.no requirements
- All data is attributed to MET Norway

## Error Handling

The service returns appropriate HTTP status codes:

- `200` - Success
- `400` - Bad Request
  - Invalid coordinates or parameters
  - Both city and coordinates provided (must use one or the other)
  - Only one coordinate provided (lat without lon or vice versa)
- `429` - Rate limit exceeded (too many requests)
- `500` - Internal Server Error
  - Data validation failures from external API
  - Internal processing errors
- `502` - Bad Gateway
  - Weather service temporarily unavailable
  - External API failures

### Error Response Format
```json
{
  "detail": "Error description"
}
```

## Rate Limiting

To protect the yr.no API from excessive requests, the service implements global rate limiting:

- **Default limit**: 20 requests per second (configurable)
- **Scope**: Global across all users
- **Storage**: Redis
- **Response**: When rate limited, returns HTTP 429 with `Retry-After` header

### Rate Limit Response Example
```json
{
  "detail": "Rate limit exceeded. Please try again later.",
  "retry_after": 2
}
```

## Configuration

Environment variables:

### Server Configuration
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `DEBUG` - Enable debug mode (default: false)

### Weather Configuration
- `TARGET_HOUR` - Target time for daily temperature (default: 14, for 2 PM)
- `TIME_TOLERANCE_HOURS` - Search window around target time (default: 2 hours)

### Redis Configuration
- `REDIS_URL` - Redis connection URL (default: redis://localhost:6379)

### Cache Configuration
- `CACHE_EXPIRE_SECONDS` - Cache TTL in seconds (default: 60)
- `CACHE_PREFIX` - Redis key prefix for cache (default: weather-forecast)

### Rate Limit Configuration
- `RATE_LIMIT_ENABLED` - Enable/disable rate limiting (default: true)
- `RATE_LIMIT_REQUESTS_PER_SECOND` - Max requests per second (default: 20)
- `RATE_LIMIT_REDIS_KEY_PREFIX` - Redis key prefix for rate limit (default: rate_limit)

### Geocoding Configuration
- `GEOCODING_USER_AGENT` - User agent for geocoding requests (default: WeatherForecastService/0.1)
- `GEOCODING_CACHE_TTL` - Geocoding cache TTL in seconds (default: 86400, 24 hours)
- `GEOCODING_CACHE_SIZE` - Maximum geocoding cache entries (default: 1000)

## Development

### Project Structure

```
src/
└── yr_forecast/
    ├── __init__.py
    ├── main.py              # FastAPI application entry point
    ├── config.py            # Configuration settings
    ├── logging_config.py    # Logging configuration
    ├── rate_limiter.py      # Rate limiting logic
    ├── api/                 # API module
    │   ├── __init__.py
    │   └── endpoints.py     # FastAPI route definitions and handlers
    ├── middleware/          # FastAPI middleware
    │   ├── __init__.py
    │   └── rate_limit.py    # Rate limiting middleware
    ├── weather/             # Weather service module
    │   ├── __init__.py
    │   ├── client.py        # HTTP client for yr.no API
    │   ├── models.py        # Pydantic data models
    │   ├── service.py       # Weather data processing service
    │   └── geocoding.py     # Geocoding utilities
    └── static/              # Static web assets
        ├── index.html       # Main HTML page (Web GUI)
        ├── css/             # CSS files
        │   └── style.css    # Main stylesheet
        └── js/              # JavaScript files
            └── app.js        # Main JavaScript application
```

## License

This project is licensed under the MIT License.

## Data Attribution

Weather data provided by [MET Norway](https://www.met.no/) and licensed under [their terms](https://api.met.no/doc/License).