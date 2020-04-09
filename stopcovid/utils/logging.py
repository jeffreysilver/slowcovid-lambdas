import logging
import sys


def _is_running_unit_tests():
    return sys.argv[0].split(" ")[-1] == "unittest"


def configure_logging():
    if _is_running_unit_tests():
        logging.disable()
        return

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
