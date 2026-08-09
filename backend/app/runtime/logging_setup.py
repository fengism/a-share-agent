import logging


def configure_logging(log_level: str, log_format: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(log_format, datefmt="%Y-%m-%d %H:%M:%S"))
        uvicorn_logger.addHandler(handler)
        uvicorn_logger.setLevel(logging.INFO)
