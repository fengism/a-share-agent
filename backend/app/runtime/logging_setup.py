import logging
from typing import TextIO


def configure_logging(log_level: str, log_format: str, *, stream: TextIO | None = None) -> None:
    """Use application request logs; expose raw Uvicorn access logs only at DEBUG."""
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

    # The request middleware already records status, duration and request/user IDs.
    # Keep server lifecycle/errors visible, without a second INFO line per request.
    root_level = logging.getLogger().getEffectiveLevel()
    logging.getLogger("uvicorn.access").setLevel(
        root_level if root_level <= logging.DEBUG else max(root_level, logging.WARNING)
    )
