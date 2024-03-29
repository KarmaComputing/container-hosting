import logging
import coloredlogs
from logging.handlers import QueueHandler, QueueListener, SMTPHandler
from TelegramHTTPHandler import TelegramHTTPHandler
import os
import sys
import queue
from dotenv import load_dotenv

load_dotenv(verbose=True)

LOGGING_SMTP_MAILHOST_PORT = int(os.getenv("LOGGING_SMTP_MAILHOST_PORT"))
LOGGING_SMTP_MAILHOST_HOST = os.getenv("LOGGING_SMTP_MAILHOST_HOST")
LOGGING_SMTP_MAILHOST = (LOGGING_SMTP_MAILHOST_HOST, LOGGING_SMTP_MAILHOST_PORT)
LOGGING_SMTP_FROMADDR = os.getenv("LOGGING_SMTP_FROMADDR")
LOGGING_SMTP_TOADDRS = os.getenv("LOGGING_SMTP_TOADDRS")
LOGGING_SMTP_SUBJECT = os.getenv("LOGGING_SMTP_SUBJECT")
LOGGING_SMTP_CREDENTIALS_EMAIL = os.getenv("LOGGING_SMTP_CREDENTIALS_EMAIL")
LOGGING_SMTP_CREDENTIALS_PASSWORD = os.getenv("LOGGING_SMTP_CREDENTIALS_PASSWORD")
LOGGING_SMTP_CREDENTIALS = (
    LOGGING_SMTP_CREDENTIALS_EMAIL,
    LOGGING_SMTP_CREDENTIALS_PASSWORD,
)
LOGGING_SMTP_SECURE = os.getenv("LOGGING_SMTP_SECURE")
if LOGGING_SMTP_SECURE == "()":
    LOGGING_SMTP_SECURE = ()
else:
    LOGGING_SMTP_SECURE = None

LOGGING_SMTP_TIMEOUT = int(os.getenv("LOGGING_SMTP_TIMEOUT"))


PYTHON_LOG_LEVEL = os.getenv("PYTHON_LOG_LEVEL", "DEBUG")
TELEGRAM_PYTHON_LOG_LEVEL = os.getenv("TELEGRAM_PYTHON_LOG_LEVEL", "ERROR")
EMAIL_LOG_LEVEL = os.getenv("EMAIL_LOG_LEVEL", "ERROR")

logger = logging.getLogger()
handler = logging.StreamHandler()  # sys.stderr will be used by default


class RequestFormatter(coloredlogs.ColoredFormatter):
    def format(self, record):
        record.url = None
        record.remote_addr = None

        return super().format(record)


formatter = RequestFormatter(
    "[%(asctime)s] %(remote_addr)s requested %(url)s %(name)-12s %(levelname)-8s %(message)s %(funcName)s %(pathname)s:%(lineno)d"  # noqa
)

handler.setFormatter(formatter)
handler.setLevel(
    PYTHON_LOG_LEVEL
)  # Both loggers and handlers have a setLevel method noqa: E501
logger.addHandler(handler)
logger.setLevel(PYTHON_LOG_LEVEL)


# Log all uncuaght exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.critical(
        "Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback)
    )  # noqa: E501


sys.excepthook = handle_exception


# Telegram logging
if os.getenv("APP_ENV", None) != "development":
    # See https://docs.python.org/3/howto/logging-cookbook.html#dealing-with-handlers-that-block # noqa
    que = queue.Queue(-1)  # no limit on size
    queue_handler = QueueHandler(que)

    telegram_token = os.getenv("TELEGRAM_TOKEN", None)
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", None)
    telegramHandlerHost = "api.telegram.org"

    telegramHandlerUrl = (
        f"bot{telegram_token}/sendMessage?chat_id={telegram_chat_id}&text="
    )

    telegramHandler = TelegramHTTPHandler(
        telegramHandlerHost, url=telegramHandlerUrl, secure=True
    )
    logger.info(
        f"Setting TELEGRAM_PYTHON_LOG_LEVEL to {TELEGRAM_PYTHON_LOG_LEVEL}"
    )  # noqa: E501
    telegramHandler.setLevel(TELEGRAM_PYTHON_LOG_LEVEL)
    listener = QueueListener(que, telegramHandler, respect_handler_level=True)
    logger.addHandler(queue_handler)
    listener.start()

    SMTP_log_que = queue.Queue(-1)  # no limit on size
    SMTP_queue_handler = QueueHandler(SMTP_log_que)

    smtpHandler = SMTPHandler(
        LOGGING_SMTP_MAILHOST,
        LOGGING_SMTP_FROMADDR,
        LOGGING_SMTP_TOADDRS,
        LOGGING_SMTP_SUBJECT,
        LOGGING_SMTP_CREDENTIALS,
        LOGGING_SMTP_SECURE,
        LOGGING_SMTP_TIMEOUT,
    )
    smtpHandler.setFormatter(formatter)
    smtpHandler.setLevel(EMAIL_LOG_LEVEL)
    SMTP_listener = QueueListener(SMTP_log_que, smtpHandler, respect_handler_level=True)

    logger.addHandler(SMTP_queue_handler)
    SMTP_listener.start()
