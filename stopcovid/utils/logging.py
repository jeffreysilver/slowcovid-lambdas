import logging
import sys


def configure_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(levelname)-8s %(asctime)s "
        "%(filename)s:%(lineno)s - %(name)s - %(funcName)s: "
        "%(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)
