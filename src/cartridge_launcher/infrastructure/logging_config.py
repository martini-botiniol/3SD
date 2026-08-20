from __future__ import annotations

import logging
from pathlib import Path


def configureLogging(logPath: Path | None = None) -> logging.Logger:
    logger = logging.getLogger("3SD")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    streamHandler = logging.StreamHandler()
    streamHandler.setFormatter(formatter)
    logger.addHandler(streamHandler)

    if logPath is not None:
        logPath.parent.mkdir(parents=True, exist_ok=True)
        fileHandler = logging.FileHandler(logPath, encoding="utf-8")
        fileHandler.setFormatter(formatter)
        logger.addHandler(fileHandler)

    return logger
