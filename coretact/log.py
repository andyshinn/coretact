import os

from loguru import logger

LOG_PATH = os.getenv("LOG_PATH")
LOGURU_FORMAT = (
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

if LOG_PATH:
    file_logger = logger.add(LOG_PATH, rotation="50 MB", retention="10 days", serialize=True, format=LOGURU_FORMAT)
