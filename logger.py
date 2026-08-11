"""core/logger.py — نظام تسجيل احترافي (Logging) يحل محل print() في كل المشروع."""
import logging
import sys

_configured = False


def get_logger(name: str) -> logging.Logger:
    global _configured
    if not _configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        ))
        root = logging.getLogger("siyada")
        root.setLevel(logging.INFO)
        root.addHandler(handler)
        _configured = True
    return logging.getLogger(f"siyada.{name}")
