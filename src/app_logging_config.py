from datetime import datetime
import logging
from logging.handlers import TimedRotatingFileHandler
import os


def loger(name="FILE"):
    if not os.path.exists("logs"):
        os.makedirs("logs")
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter("%(name)s - %(levelname)s - %(message)s")
    )

    logging.basicConfig(
        handlers=[
            TimedRotatingFileHandler("logs/my_log.log", backupCount=10),
            console_handler,
        ],
        level=logging.DEBUG,
        format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logger = logging.getLogger(name)

    logger.info("App Started")
    return logger


def setup_logger(logger_name):
    logger = logging.getLogger(logger_name)
    if not os.path.exists("logs"):
        os.makedirs("logs")
    date_str = datetime.now().strftime("%Y-%m-%d")
    fh = TimedRotatingFileHandler(
        f"logs/file_{date_str}.log", when="midnight", interval=1, backupCount=7
    )
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.setLevel(logging.INFO)
    # create file handler which logs even debug messages
    # fh = logging.FileHandler(logfile)
    # fh.setLevel(logging.INFO)
    # create console handler with a higher log level
    # ch = logging.StreamHandler()
    # ch.setLevel(logging.INFO)
    # create formatter and add it to the handlers

    # ch.setFormatter(formatter)
    # add the handlers to the logger

    # logger.addHandler(ch)
    return logger


# setup the logger as below with mylogger being the name of the #logger and myloggerfile.log being the name of the logfile
# mylogger = setup_logger("mylogger", "myloggerfile.log")
# mylogger.info("My Logger has been initialized")
