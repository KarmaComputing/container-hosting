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

    # Inform SITE_ADMIN
    log.info(f"signal_subscriber_new_repo signal caught by sender {sender}")
    send_email(
        "New repo created", SITE_ADMIN_EMAIL, SITE_ADMIN_EMAIL, "New repo created"
    )

    # Inform user
    app_url = ""
    repo_name = ""
    user_email = ""
    avatar_url = ""
    github_username = ""
    github_repo_origin = ""

    if "app_url" in sender:
        app_url = sender["app_url"]
    if "repo_name" in sender:
        repo_name = sender["repo_name"]
    if "user_email" in sender:
        user_email = sender["user_email"]
    if "avatar_url" in sender:
        avatar_url = sender["avatar_url"]
    if "github_username" in sender:
        github_username = sender["github_username"]
    if "github_repo_origin" in sender:
        github_repo_origin = sender["github_repo_origin"]

    subject = f"Your Container Hosting is ready {github_username}!🚀"
    body = f""""Welcome {github_username}!\n\n
    Your container is hosted at: {app_url}\n\n
    Your container hosting repo is setup here: {github_repo_origin}\n\n
    Your app name and repo name is currently: {repo_name}\n\n
    """

    send_email(subject, SITE_ADMIN_EMAIL, user_email, body)


# Bind Signals to subscribers
signal_new_repo.connect(signal_subscriber_new_repo)
