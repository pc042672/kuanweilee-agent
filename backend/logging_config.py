"""
Centralized logging configuration.

Phase 1-2: File-based logging with daily rotation.
Phase 3: Add Cloud Trace / Cloud Logging / Cloud Monitoring exporters.

Usage:
    from logging_config import setup_logging
    setup_logging()  # call once at server startup
"""

import logging
import os
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

import settings

_LOG_DIR = Path(__file__).resolve().parent / "logs"
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s | %(message)s"
_LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"
_initialized = False


def setup_logging(
    level: str = None,
    log_dir: str = None,
    enable_cloud: bool = None,
) -> None:
    """Configure logging for the application. Idempotent — safe to call multiple times.

    Args:
        level: Log level (default: LOG_LEVEL env var or INFO).
        log_dir: Directory for log files (default: backend/logs/).
        enable_cloud: Enable Cloud Logging exporter (default: ENABLE_CLOUD_LOGGING env var).
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    level = level or settings.LOG_LEVEL
    log_dir = Path(log_dir) if log_dir else _LOG_DIR
    enable_cloud = enable_cloud if enable_cloud is not None else settings.ENABLE_CLOUD_LOGGING

    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_LOG_DATEFMT)

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = TimedRotatingFileHandler(
        filename=log_dir / "ai-cdp.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    file_handler.suffix = "%Y-%m-%d"
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    error_handler = TimedRotatingFileHandler(
        filename=log_dir / "ai-cdp-error.log",
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    error_handler.suffix = "%Y-%m-%d"
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root.addHandler(error_handler)

    # Phase 3: Cloud Logging
    if enable_cloud:
        _setup_cloud_logging(root)

    # Quiet noisy third-party loggers
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("google.auth").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logging.getLogger("ai_cdp").info(
        "Logging initialized: level=%s, dir=%s, cloud=%s",
        level, log_dir, enable_cloud,
    )


def _setup_cloud_logging(root_logger: logging.Logger) -> None:
    """Attach Google Cloud Logging handler (Phase 3).

    Requires: pip install google-cloud-logging
    Env: GCP_PROJECT_ID or Application Default Credentials
    """
    try:
        import google.cloud.logging as cloud_logging
        client = cloud_logging.Client()
        cloud_handler = cloud_logging.handlers.CloudLoggingHandler(
            client, name="ai-cdp"
        )
        cloud_handler.setLevel(logging.INFO)
        root_logger.addHandler(cloud_handler)
        root_logger.info("Cloud Logging handler attached")
    except ImportError:
        root_logger.warning(
            "google-cloud-logging not installed, skipping Cloud Logging"
        )
    except Exception as e:
        root_logger.warning("Failed to initialize Cloud Logging: %s", e)
