import logging
from typing import TextIO


def configure_logging(log_level: str, log_format: str, *, stream: TextIO | None = None) -> None:
    """Configure one root handler and let Uvicorn loggers propagate to it."""
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=stream,
        force=True,
    )
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.setLevel(logging.NOTSET)
        uvicorn_logger.propagate = True
