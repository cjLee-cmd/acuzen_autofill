"""Logging helpers for the MedDRA autofill automation."""
from __future__ import annotations

import json
import logging
from logging import LogRecord
from pathlib import Path
from typing import Any, Dict


class JsonFormatter(logging.Formatter):
    """Formats log records as single line JSON objects."""

    def format(self, record: LogRecord) -> str:
        payload: Dict[str, Any] = {
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.__dict__.get("job_id"):
            payload["job_id"] = record.__dict__["job_id"]
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(log_path: str | Path | None = None) -> None:
    """Configure root logger to use JSON formatting."""
    handler: logging.Handler
    if log_path:
        path = Path(log_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, encoding="utf-8")
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler])


__all__ = ["configure_logging", "JsonFormatter"]
