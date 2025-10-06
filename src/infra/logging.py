from __future__ import annotations

from loguru import logger
from pathlib import Path
import sys


def setup_logging(verbose: bool = False, log_dir: str | Path = "logs") -> None:
    """Configure loguru for console + rotating file logs.

    Args:
        verbose: enable DEBUG level on console.
        log_dir: directory to store rotating logs.
    """
    logger.remove()

    level = "DEBUG" if verbose else "INFO"
    logger.add(
        sys.stdout,
        level=level,
        enqueue=True,
        backtrace=False,
        diagnose=False,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    )

    Path(log_dir).mkdir(parents=True, exist_ok=True)
    logger.add(
        Path(log_dir) / "bot.log",
        level="DEBUG",
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    # Prevent secrets from leaking by default; call logger.bind(safe=True) where needed
