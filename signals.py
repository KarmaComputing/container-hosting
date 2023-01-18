from blinker import signal
from logger import logger
from email_tools import send_email
import os

log = logger

SITE_ADMIN_EMAIL = os.getenv("SITE_ADMIN_EMAIL")

# Signals
signal_new_repo = signal("signal_new_repo")

# Signal subscribers:


def signal_subscriber_new_repo(sender):
    log.info(f"signal_subscriber_new_repo signal caught by sender {sender}")
    send_email(
        "New repo created", SITE_ADMIN_EMAIL, SITE_ADMIN_EMAIL, "New repo created"
    )


# Bind Signals to subscribers
signal_new_repo.connect(signal_subscriber_new_repo)
