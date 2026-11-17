import json
import logging
from datetime import UTC, datetime


class JsonFormatter(logging.Formatter):
    """One JSON object per line on stdout, so any log collector can parse it."""

    def format(self, record):
        entry = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)
