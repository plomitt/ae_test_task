"""Main FastAPI application for weather forecast service."""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
import uvicorn
import traceback
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend

from yr_forecast.api.endpoints import router as weather_router
from yr_forecast.config import HOST, PORT, DEBUG, REDIS_URL, CACHE_PREFIX

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan manager."""
    try:
        # Initialize Redis cache
        logger.info(f"Connecting to Redis at {REDIS_URL}")
        redis_client = redis.from_url(REDIS_URL)
        FastAPICache.init(RedisBackend(redis_client), prefix=CACHE_PREFIX)
        logger.info("Cache initialized with Redis backend")

        # Verify cache is working
        backend = FastAPICache.get_backend()
        logger.info(f"Cache backend active: {backend}")

        logger.info("Starting Yr.no Weather Forecast Service")
        yield
    except Exception as e:
        logger.error(f"Startup error: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        try:
            logger.info("Shutting down Yr.no Weather Forecast Service")
        except Exception as e:
            logger.error(f"Shutdown error: {e}")


def create_app() -> FastAPI:
    """Create and configure FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Yr.no Weather Forecast Service",
        description="REST API service that provides daily weather forecasts using MET Norway's yr.no API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routers
    app.include_router(weather_router)

    # Root endpoint
    @app.get("/", tags=["root"])
    async def root() -> dict:
        """Root endpoint with basic service information.

        Returns:
            Basic service information
        """
        return {
            "message": "Yr.no Weather Forecast Service",
            "docs": "/docs",
            "redoc": "/redoc",
            "weather": "/weather",
            "health": "/weather/health"
        }

    return app


# Create app instance for uvicorn
app = create_app()


def main() -> None:
    """Main entry point for the application."""
    logger.info(f"Starting server on {HOST}:{PORT}")
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        reload=DEBUG,
        log_level="info" if not DEBUG else "debug"
    )


if __name__ == "__main__":
    main()