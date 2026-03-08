import os
import sys

from loguru import logger

LOG_FORMAT = (
    "<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | "
    "{name}:{function}:{line} - <level>{message}</level>"
)
logger.add(sys.stderr, level=os.environ.get("LOG_LEVEL", "INFO").upper(), format=LOG_FORMAT)
