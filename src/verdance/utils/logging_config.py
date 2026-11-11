import sys
from pathlib import Path

from loguru import logger

# Sink ids verdance has added, so repeated setup replaces only our own sinks
_SINK_IDS: list[int] = []
_REMOVED_DEFAULT = False


def setup_logger(log_path: str | Path, log_level: str = "WARNING") -> None:
    """Send verdance logs to stderr and log_path, replacing only verdance's own sinks.

    A host application's loguru sinks are left intact (unlike a blanket
    ``logger.remove()``); repeated calls replace the sinks verdance added rather
    than accumulating them. loguru's default stderr handler is dropped once so
    CLI output is not doubled.
    """
    global _SINK_IDS, _REMOVED_DEFAULT
    fmt = "{time:YYYY-MM-DD HH:mm} - {level} - {message}"

    for sink_id in _SINK_IDS:
        try:
            logger.remove(sink_id)
        except ValueError:
            pass
    if not _REMOVED_DEFAULT:
        # drop loguru's default stderr handler (id 0) once; an embedding app that
        # manages its own sinks has already replaced it
        try:
            logger.remove(0)
        except ValueError:
            pass
        _REMOVED_DEFAULT = True

    _SINK_IDS = [
        logger.add(sys.stderr, level=log_level, format=fmt),
        logger.add(log_path, level=log_level, encoding="utf-8", format=fmt),
    ]
