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

    app_url = ""
    repo_name = ""
    user_email = ""
    avatar_url = ""
    github_username = ""
    github_repo_origin = ""
    AMBER_SECRET = ""

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
        github_repo_url = f"https://github.com/{github_username}/{repo_name}"
    if "AMBER_SECRET" in sender:
        AMBER_SECRET = sender["AMBER_SECRET"]
        SECRETS_URL = (
            f"https://github.com/{github_username}/{repo_name}/settings/secrets/actions"
        )

    # Inform SITE_ADMIN
    body = f"""Github username: {github_username}!\n\n
    email: {user_email}\n\n
    app_url: {app_url}\n\n
    github_repo_url: {github_repo_url}\n\n
    APP_NAME: {repo_name}\n\n\n\n
    """
    send_email(
        "New repo created for {github_username}",
        SITE_ADMIN_EMAIL,
        SITE_ADMIN_EMAIL,
        body,
    )

    # Inform user
    subject = f"Your Container Hosting is ready {github_username}!🚀"
    body = f"""Welcome {github_username}!\n\n
    Your container is hosted at: {app_url}\n\n
    Your container hosting repo is setup here: {github_repo_url}\n\n
    Your app name and repo name is currently: {repo_name}\n\n\n\n
    Your AMBER_SECRET (to store app secrets) is "{AMBER_SECRET}".\n
    We recommend you change your AMBER_SECRET as soon as possible and save the\n
    new value also at {SECRETS_URL}.\n\n\n\n
    Welcome to container hosting!
    """

    send_email(subject, SITE_ADMIN_EMAIL, user_email, body)


# Bind Signals to subscribers
signal_new_repo.connect(signal_subscriber_new_repo)
