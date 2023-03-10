import logging
import sys


def get_logger() -> logging.Logger:
    return logging.getLogger("whispermovie")


def init_logger() -> None:
    """
    Initialize the logger. Log to stdout by default.
    """
    logger = get_logger()
    logger.setLevel(level=logging.INFO)

    fmt = '[%(asctime)s] (%(levelname)s) %(message)s'
    datefmt = '%Y-%m-%d %H:%M:%S'

    formatter = logging.Formatter(fmt, datefmt)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level=logging.DEBUG)  # Print all the logs.
    handler.setFormatter(formatter)
    logger.addHandler(handler)
