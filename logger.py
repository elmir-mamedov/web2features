import logging
import os
from datetime import datetime


def setup_logger(log_dir: str = "logs") -> logging.Logger:
    """
    Sets up a logger that writes to both console and a timestamped log file.
    """
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"pipeline_{timestamp}.log")

    logger = logging.getLogger("web2features")
    logger.setLevel(logging.DEBUG)

    # avoid duplicate handlers if called multiple times
    if logger.handlers:
        return logger

    # file handler — DEBUG level, captures everything
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)

    # console handler — INFO level, only important stuff
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.info(f"Logging to {log_file}")
    return logger