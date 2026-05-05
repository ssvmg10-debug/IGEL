# my_logger.py
"""The Python logger is used to record automation events with different severity levels and route them to configurable
outputs to the console and log files for debugging and monitoring purposes."""

import logging
import sys, os
import datetime
import inspect

sys.path.append(".")
sys.path.append("..")

from config.read_config import root_path, logging_level
print(logging_level['logLevel'])


if not logging_level:
    logging_level['logLevel']='INFO'


def getLogger(filename=None):
    try:
        current_time = datetime.datetime.now().strftime("%d-%m-%y-%H%M%S")

        loggerName = inspect.stack()[1][3]
        logger = logging.getLogger(loggerName)

        baseDir = os.path.join(root_path, "Logs")
        if (not os.path.exists(baseDir)):
            os.makedirs(baseDir)
        dir_name = "Logs-" + current_time
        logDir = os.path.join(baseDir, dir_name)
        if not os.path.exists(logDir):
            os.makedirs(logDir)
        log_path = logDir
        if (filename == None):
            filename = "logfile-" + current_time + ".log"

        log_file = os.path.join(logDir, filename)
        fileHandler = logging.FileHandler(log_file)
        logger.handlers.clear()
        formatter = logging.Formatter("%(asctime)s: %(levelname)s: "
                                      "%(filename)s: %(funcName)s: "
                                      "%(lineno)d: %(message)s ")
        fileHandler.setFormatter(formatter)

        logger.addHandler(fileHandler)  # filehandler object

        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        #logger.setLevel(logging.DEBUG)
        logger.setLevel(logging_level['logLevel'])
        return logger, logDir
    except Exception as e:
        logging.error("Log file creation failure", e)
        sys.exit(2)


logger,logDir=getLogger()
