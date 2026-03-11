import logging
import sys

LOG_FORMAT = "[%(asctime)s - %(levelname)s - %(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> (
    None
):  # TODO Maybe use config.ini to provide a default configuration for file logging
    """
    Set up a Basic logger that will be configured when using the Trainer Interface.
    If User does not use the interface logs will be displayed with the current configuration

    Returns:
        None
    """
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        force=True,
    )
