# Yr.no Weather Forecast Service

A REST API service that provides daily weather forecasts using MET Norway's yr.no API. The service returns temperature data for approximately 14:00 local time for as many forecast days as available.

## Features

- Daily temperature forecasts at ~14:00 (within 2 hours) local time
- Custom location support (latitude/longitude)
- Default location: Belgrade, Serbia
- Automatic API documentation (OpenAPI/Swagger)
- Proper timezone handling
- Input validation and error handling

## Quick Start

### Using Docker (Recommended)

1. **Docker compose:**
   ```bash
   docker-compose up -d
   ```

2. **Access the API:**
   - API documentation: http://localhost:8000/docs
   - Get weather: http://localhost:8000/weather/

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

## API Endpoints

### Get Weather Forecast

**GET** `/weather`

Returns forecast for the default location (Belgrade).

**GET** `/weather?lat={latitude}&lon={longitude}&city={city_name}`

Returns forecast for custom coordinates.

#### Parameters

- `lat` (optional): Latitude in decimal degrees (-90 to 90)
- `lon` (optional): Longitude in decimal degrees (-180 to 180)
- `city` (optional): City name for display purposes
- `timezone` (optional): Timezone identifier (default: Europe/Belgrade)

#### Example Requests

```bash
# Get Belgrade forecast (default)
curl http://localhost:8000/weather/

# Get Paris forecast
curl "http://localhost:8000/weather/?lat=48.8575&lon=2.3514&city=Paris"

# Get forecast with custom timezone
curl "http://localhost:8000/weather/?lat=52.5200&lon=13.4050&city=Berlin&timezone=Europe/Berlin"
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
- User-Agent header is properly set according to yr.no requirements
- All data is attributed to MET Norway

## Error Handling

The service returns appropriate HTTP status codes:

- `200` - Success
- `400` - Invalid coordinates or parameters
- `404` - No forecast data available
- `500` - Internal server error
- `502` - Weather service temporarily unavailable

## Configuration

Environment variables:

- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `DEBUG` - Enable debug mode (default: false)

## Development

### Project Structure

```
src/
└── yr_forecast/
    ├── __init__.py
    ├── main.py              # FastAPI application
    ├── config.py            # Configuration settings
    ├── weather/
    │   ├── __init__.py
    │   ├── client.py        # yr.no API client
    │   ├── models.py        # Pydantic data models
    │   └── service.py       # Weather data processing
    └── api/
        ├── __init__.py
        └── endpoints.py     # API routes
```

## License

This project is licensed under the MIT License.

## Data Attribution

Weather data provided by [MET Norway](https://www.met.no/) and licensed under [their terms](https://api.met.no/doc/License).