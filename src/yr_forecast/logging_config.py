"""Centralized logging configuration."""

import logging


def configure_logging():
    """
    Configure a consistent logging format for the entire application.
    """
    # Define the standard formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Configure the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Create a console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # Add the handler to the root logger
    root_logger.addHandler(console_handler)

    # Configure specific third-party loggers to use the same format
    loggers_to_configure = [
        "uvicorn",
        "uvicorn.access",
        "uvicorn.error",
        "httpx",
        "fastapi",
    ]

    for logger_name in loggers_to_configure:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)

        # Remove existing handlers to avoid duplicate logs
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

        # Don't propagate to avoid duplicate messages
        logger.propagate = False

        # Create a dedicated handler for each logger
        handler = logging.StreamHandler()
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)

        logger.addHandler(handler)