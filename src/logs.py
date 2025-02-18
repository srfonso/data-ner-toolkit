import os
import logging
import logging.handlers as logger_handlers
from datetime import datetime
from src.settings import LOG_DIR
from argparse import ArgumentTypeError


LOG_SUFFIX = "%Y%m%d_%H.log"


def setup_logging(name):
    #logging.setLoggerClass(Logger) # Personalized Logger class
    return logging.getLogger(name)

def valid_loglevel(loglevel):
    if loglevel not in logging._nameToLevel.keys():
         raise ArgumentTypeError(
            "Not a valid level for loggings: {0!r}".format(loglevel)
        )
    return loglevel

def configure_logging(loglevel, log_dir=LOG_DIR):
    """
    Configure logging to output:
      - Stream logs (to stdout) for messages >= loglevel.
      - A file with debug/info logs.
      - A file with warning/error logs.
    
    Log file names follow the convention: logs_<type>_<timestamp>.log
    """

    class MaxLevelFilter(logging.Filter):
        def __init__(self, max_level):
            super().__init__()
            self.max_level = max_level

        def filter(self, record):
            return record.levelno < self.max_level

    # Ensure the log directory exists.
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Get the root logger and remove any previously added handlers.
    rootLogger = logging.getLogger()

    # Set the root logger level low so that all messages are passed to handlers.
    # (Handlers themselves will filter as needed.)
    rootLogger.setLevel(logging.DEBUG)

    # Create a common formatter.
    formatter = logging.Formatter(
        '{asctime}.{msecs:03.0f}|{levelname}|{name}|{message}', 
        datefmt = '%Y-%m-%d %H:%M:%S', 
        style = '{'
    )

    # 1. Create the stream (console) handler.
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(loglevel)
    stream_handler.setFormatter(formatter)
    rootLogger.addHandler(stream_handler)

    # 2. Create the debug/info file handler.
    debug_log_file = os.path.join(log_dir, "logs_debugInfo.log")
    debug_handler = logger_handlers.TimedRotatingFileHandler(
        debug_log_file,
        when='H',
        interval=4,
        backupCount=24,
        encoding="utf-8"
    )
    debug_handler.suffix = LOG_SUFFIX
    debug_handler.setLevel(logging.DEBUG)
    # Only allow messages below WARNING (i.e. DEBUG and INFO).
    debug_handler.addFilter(MaxLevelFilter(logging.WARNING))
    debug_handler.setFormatter(formatter)
    rootLogger.addHandler(debug_handler)

    # 3. Create the warning/error file handler.
    warning_log_file = os.path.join(log_dir, "logs_warningError.log")
    warning_handler = logger_handlers.TimedRotatingFileHandler(
        warning_log_file,
        when='H',
        interval=4,
        backupCount=24,
        encoding="utf-8"
    )
    warning_handler.suffix = "%Y%m%d_%H.log"
    # This handler only cares about WARNING and above.
    warning_handler.setLevel(logging.WARNING)
    warning_handler.setFormatter(formatter)
    rootLogger.addHandler(warning_handler)