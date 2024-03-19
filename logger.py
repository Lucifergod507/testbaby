import logging

def get_logger(name, level = logging.DEBUG) -> logging.Logger:
    logger = logging.getLogger(name)
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            '%(asctime)s - %(name)s - '
            '%(levelname)s - %(message)s'
        )
    )
    logger.addHandler(handler)
    logger.setLevel(level)
    return logger
