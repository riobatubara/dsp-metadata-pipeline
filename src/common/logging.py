import logging
import os
import sys
from src.common.config import settings

# How to use
# from src.common.logging import logger

# logger.info("Starting Spotify extraction")
# logger.warning("Missing release date")
# logger.error("Failed to connect to PostgreSQL")

def setup_logging() -> logging.Logger:
    """
    Configure and return the application logger.

    Log level can be controlled with the LOG_LEVEL environment variable.
    Example:
        LOG_LEVEL=DEBUG
    """
    log_level = settings.log_level

    logger = logging.getLogger("dsp_metadata_pipeline")

    # Avoid adding duplicate handlers when Airflow reloads/imports modules.
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, log_level, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logger.level)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.propagate = False

    return logger


logger = setup_logging()