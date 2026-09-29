"""Small allowlisted JSON logger; never emits questions, SQL, rows, or model text."""

import json
import logging
from datetime import datetime, timezone


LOG_FIELDS = (
    "request_id", "analysis_id", "job_id", "workspace_id", "stage", "status",
    "method", "path", "duration_ms", "error_type", "count",
)


class SafeJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "at": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        payload.update({key: getattr(record, key) for key in LOG_FIELDS if hasattr(record, key)})
        return json.dumps(payload, separators=(",", ":"), default=str)


class SafeStreamHandler(logging.StreamHandler):
    pass


def configure_datatalk_logging() -> None:
    logger = logging.getLogger("datatalk")
    if any(isinstance(handler, SafeStreamHandler) for handler in logger.handlers):
        return
    handler = SafeStreamHandler()
    handler.setFormatter(SafeJsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
