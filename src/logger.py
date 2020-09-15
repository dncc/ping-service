import logging
from logging.handlers import RotatingFileHandler
try:
    from .config import get_config
except:
    from config import get_config

LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}


def get_logger(name='ping-service', add_console_handler=False):
    params = get_config('logging')

    formater = logging.Formatter(params['format'])

    file_handler = RotatingFileHandler(params['file_path'],
                                       maxBytes=int(params['max_bytes']),
                                       backupCount=int(params['max_backups']))
    file_handler.setFormatter(formater)

    logger = logging.getLogger(name)
    logger.setLevel(LEVELS.get(params['level'], logging.INFO))
    logger.addHandler(file_handler)

    if add_console_handler:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formater)
        logger.addHandler(console_handler)

    return logger
