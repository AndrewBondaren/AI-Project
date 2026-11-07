import logging

from app.core.logging.contracts import LogConsumer


def get_consumer_logger(consumer: LogConsumer) -> logging.Logger:
    if type(consumer) is not LogConsumer:
        raise TypeError("expected LogConsumer")
    return logging.getLogger(consumer.value)
