from starlette.applications import Starlette
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from starlette.requests import Request

from logger import logger

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

import os
import requests
import json
from base64 import b64encode
from nacl import encoding, public

from git import Repo
import shutil

import secrets
from dotenv import load_dotenv
import subprocess
from signals import signal_new_repo
import string
from pathlib import Path
import stat

"""
Create automated deploys for repos both new and existing

Key steps are:

    - 1: Get Git host (e.g. Github) auth token from user
    - 2: Decision point:
        a: - Create new repo from scratch as a quickstart repo
        b: - Update an existing repo with container hosting
"""

log = logger

load_dotenv(verbose=True)

templates = Jinja2Templates(directory="templates")

BASE_PATH = os.getenv("BASE_PATH")
GITHUB_OAUTH_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID")
GITHUB_OAUTH_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI")
DOKKU_HOST = os.getenv("DOKKU_HOST")
DOKKU_HOST_SSH_ENDPOINT = os.getenv("DOKKU_HOST_SSH_ENDPOINT")
CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY = os.getenv(
    "CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY"
)
DOKKU_WRAPPER_FULL_PATH = os.getenv("DOKKU_WRAPPER_FULL_PATH")

# See https://github.com/dokku/dokku-letsencrypt/pull/211


def amber_encrypt(key: str, value: str, amber_file_location="./amber.yaml"):
    if os.getenv("AMBER_YAML") is not None:
        amber_file_location = os.getenv("AMBER_YAML")
    subprocess.run(
        ["amber", "encrypt", "--amber-yaml", amber_file_location, key, value]
    )


def generate_ssh_keys():
    """Generate public/private ssh keys

    See also https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/ # noqa: E501
    """
    key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )

    # Derive public key
    public_key = key.public_key().public_bytes(
        serialization.Encoding.OpenSSH, serialization.PublicFormat.OpenSSH
    )

    # Serialize private_key to OpenSSH format
    openSSH = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        # use BestAvailableEncryption is want password protected key
        # encryption_algorithm=serialization.BestAvailableEncryption(b'mypassword')
        # Create key with no password
        encryption_algorithm=serialization.NoEncryption(),
    )
    return public_key, openSSH


def encrypt_github_secret(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the GitHub repo public key.
    Used for creating GitHub repo secrets
    """
    public_key = public.PublicKey(
        public_key.encode("utf-8"), encoding.Base64Encoder()
    )  # noqa: E501
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")


async def homepage(request):
    """Homepage and display connect Github link"""
    log.debug("Homepage")
    client_id = GITHUB_OAUTH_CLIENT_ID
    state = f"{secrets.token_urlsafe(30)}---no-framework"
    state_rails = f"{secrets.token_urlsafe(30)}---rails"
    state_django = f"{secrets.token_urlsafe(30)}---django"
    state_flask = f"{secrets.token_urlsafe(30)}---flask"
    # UNTRUSTED_REPO_INFO gets replaced by the users given git host, org name and repo name
    state_existing_repo = f"{secrets.token_urlsafe(30)}---existing_repo-UNTRUSTED_GIT_HOST|UNTRUSTED_GIT_ORG_NAME|UNTRUSTED_GIT_REPO_NAME"

    github_oauth_auth_url = "https://github.com/login/oauth/authorize?"

    github_authorize_url = f"{github_oauth_auth_url}client_id={client_id}&state={state}&scope=workflow%20repo%20user:email"  # noqa: E501
    github_authorize_url_rails = f"{github_oauth_auth_url}client_id={client_id}&state={state_rails}&scope=workflow%20repo%20user:email"  # noqa: E501
    github_authorize_url_django = f"{github_oauth_auth_url}client_id={client_id}&state={state_django}&scope=workflow%20repo%20user:email"  # noqa: E501
    github_authorize_url_flask = f"{github_oauth_auth_url}client_id={client_id}&state={state_flask}&scope=workflow%20repo%20user:email"  # noqa: E501
    github_authorize_url_existing_repo = f"{github_oauth_auth_url}client_id={client_id}&state={state_existing_repo}&scope=workflow%20repo%20user:email"  # noqa: E501

    return templates.TemplateResponse(
        "index.html",
        {
            "github_authorize_url": github_authorize_url,
            "github_authorize_url_rails": github_authorize_url_rails,
            "github_authorize_url_django": github_authorize_url_django,
            "github_authorize_url_flask": github_authorize_url_flask,
            "github_authorize_url_existing_repo": github_authorize_url_existing_repo,
            "request": request,
        },
    )


async def githubcallback(request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    # Validate state token matches what we sent when
    # generating the auth url

    # TODO check if already authorised
    # Get access token by POST'ing to github access token endpoint
    data = {
        "client_id": GITHUB_OAUTH_CLIENT_ID,
        "client_secret": GITHUB_OAUTH_CLIENT_SECRET,
        "code": code,
        "redirect_uri": GITHUB_OAUTH_REDIRECT_URI,
    }
    headers = {"Accept": "application/json"}
    req = requests.post(
        "https://github.com/login/oauth/access_token",
        data=data,
        headers=headers,  # noqa: E501
    )

    # Get access token from github
    resp = req.json()
    access_token = resp.get("access_token")
    scope = resp.get("scope")
    print(scope)
    print(access_token)

    # Use access token
    headers = {"Authorization": f"token {access_token}"}
    headers["Accept"] = "application/vnd.github+json"

    # Get GitHub user information
    req = requests.get("https://api.github.com/user", headers=headers).json()
    # Get their GitHub username
    username = req.get("login")
    log.info("Set git_org to username {username}")
    git_org = username
    avatar_url = req.get("avatar_url")
    log.info(f"avatar_url: {avatar_url}")
    # Get email address so can do git commits with correct author information
    req = requests.get("https://api.github.com/user/emails", headers=headers)
    email = req.json()[0].get("email", None)

    # Create unique app name for this apps container hosting
    random_string = secrets.token_urlsafe(5).lower().replace("_", "")
    APP_NAME = f"container-{random_string}"

    # Create api key for container-hosting
    CONTAINER_HOSTING_API_KEY = f"secret_{secrets.token_urlsafe(60)}"

    # Create hostname for app
    app_host = f"container-{random_string}.containers.anotherwebservice.com"
    app_url = f"https://container-{random_string}.containers.anotherwebservice.com/"  # noqa: E501
    if "---existing_repo-" in state:
        # In this case don't create a new repo, only
        # add to the existing repo provided in ---existing_repo-.. metadata
        # example state:
        # mT4D4deeuV7VJDiYwMHZ_9Wk2DTZYEgUKvyzgEzD---existing_repo-github.com|KarmaComputing|container-hosting
        # which we split into unsafe_git_host, unsafe_git_org, unsafe_repo_name

        allowed_chars = string.ascii_lowercase + string.ascii_uppercase + "-" + "."
        unsafe_git_host, unsafe_git_org, unsafe_repo_name = state.split(
            "---existing_repo-"
        )[1].split("|")

        for char in unsafe_git_host:
            if char not in allowed_chars:
                log.error("Disallowed char in unsafe_git_host")
                exit(-1)
        git_host = unsafe_git_host

        for char in unsafe_git_host:
            if char not in allowed_chars:
                log.error("Disallowed char in unsafe_git_org")
                exit(-1)
        git_org = unsafe_git_org

        for char in unsafe_repo_name:
            if char not in allowed_chars:
                log.error("Disallowed char in unsafe_repo_name")
                exit(-1)
        repo_name = unsafe_repo_name

        repo_url = f"https://{git_host}/{git_org}/{repo_name}"

    if "---existing_repo-" not in state:
        repo_name = APP_NAME  # Because we're creating a repo from scratch

        # Prepare directory for new git repo
        os.makedirs(f"./tmp-cloned-repos/{APP_NAME}", exist_ok=True)

        # Create a new repo for organisation user has access to
        # req = requests.post("https://api.github.com/orgs/karmacomputing/repos", headers=headers, data=json.dumps(data))
        # Create repo for authenticated user
        data = {
            "name": APP_NAME,
            "description": "Created using https://container-hosting.anotherwebservice.com/#start",  # noqa: E501
            "homepage": app_url,
            "private": False,
            "has_issues": True,
            "has_projects": True,
            "has_wiki": True,
        }
        req = requests.post(
            "https://api.github.com/user/repos", headers=headers, data=json.dumps(data)
        )
        repo_url = req.json()["html_url"]

    log.info(f"New container host creating at: {repo_url}")

    # Prepare amber secret
    amber_file_location = f"./tmp-cloned-repos/{APP_NAME}/amber.yaml"

    # Create repo secrets
    req = requests.get(
        f"https://api.github.com/repos/{git_org}/{repo_name}/actions/secrets/public-key",
        headers=headers,
    ).json()

    # Check access
    try:
        if req["message"] == "Must have admin rights to Repository.":
            return HTMLResponse(
                "<h1>Oops sorry please click 'grant' first- here's what you need to do:</h1><p>It looks like you forgot to click 'Grant' access during the oauth flow. You must first grant access to <em>your</em> repo/organisation (and have admin rights to that Repository).<br />How? Follow these steps:<br />Try again using incognito mode, and remember to first click 'Grant' next to your organisation name, and <em>then</em> press the green 'Authorize' button. <a href='/'>Open this link in incognito mode and try again.</a><br />Note: You can revoke access at any time by visiting https://github.com/organizations/<your-organization-name/settings/oauth_application_policy</p><br /><img src='/static/grant-permissions-how-to.png' style='max-width: 500px' />",
                status_code=403,
            )
    except Exception as e:
        log.error(f"Exception getting repo public key: {e}")

    github_repo_public_key = req["key"]
    github_repo_public_key_id = req["key_id"]

    def github_store_secret(SECRET_NAME, SECRET_VALUE: str):
        secret_Encrypted = encrypt_github_secret(github_repo_public_key, SECRET_VALUE)
        data = {
            "encrypted_value": secret_Encrypted,
            "key_id": github_repo_public_key_id,
        }
        req = requests.put(  # noqa: 203
            f"https://api.github.com/repos/{git_org}/{repo_name}/actions/secrets/{SECRET_NAME}",
            headers=headers,
            data=json.dumps(data),
        )

    # Create DOKKU_SSH_PRIVATE_KEY
    public_key, private_key = generate_ssh_keys()
    # Restrict public_key ssh commands
    public_key = f'command="{DOKKU_WRAPPER_FULL_PATH}",no-agent-forwarding,no-user-rc,no-X11-forwarding,no-port-forwarding {public_key.decode("utf-8")}'
    # POST public key to DOKKU_HOST_SSH_ENDPOINT
    data = {
        "CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY": CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY,
        "public_key": public_key,
    }
    req = requests.post(DOKKU_HOST_SSH_ENDPOINT, json=data)
    # POST CONTAINER_HOSTING_API_KEY to DOKKU_HOST_SSH_ENDPOINT
    data = {
        "CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY": CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY,
        "APP_NAME": APP_NAME,
        "CONTAINER_HOSTING_API_KEY": CONTAINER_HOSTING_API_KEY,
    }
    req = requests.post(
        DOKKU_HOST_SSH_ENDPOINT + "/CONTAINER_HOSTING_API_KEY", json=data
    )

    # Write out private_key
    with open("./private_key", "wb") as fp:
        fp.write(private_key)

    # Write out public_key
    with open("./private_key.pub", "wb") as fp:
        fp.write(public_key.encode("utf-8"))

    # Set Repo Secret DOKKU_SSH_PRIVATE_KEY
    DOKKU_SSH_PRIVATE_KEY_Encrypted = encrypt_github_secret(
        github_repo_public_key, private_key.decode("utf-8")
    )
    data = {
        "encrypted_value": DOKKU_SSH_PRIVATE_KEY_Encrypted,
        "key_id": github_repo_public_key_id,
    }
    req = requests.put(
        f"https://api.github.com/repos/{git_org}/{repo_name}/actions/secrets/DOKKU_SSH_PRIVATE_KEY",
        headers=headers,
        data=json.dumps(data),
    )

    # Create README.md if does not already exist
    readme_url = (
        f"https://api.github.com/repos/{git_org}/{repo_name}/contents/README.md"
    )

    # Send the GET request with Basic Auth
    response = requests.get(readme_url, headers=headers)

    # Check if the README.md file exists
    README_ALREADY_EXISTS = False
    if response.status_code == 200:
        README_ALREADY_EXISTS = True
        print("README.md file exists in the repository.")
    else:
        print("README.md file does not exist in the repository.")

    if README_ALREADY_EXISTS is False:
        REPO_CLONE_URL = f"git@github.com:{git_org}/{repo_name}.git"
        with open("./repo-template-files/README.md") as fp:
            readme_md = fp.read()
            readme_md = readme_md.replace("APP_URL", app_url)
            readme_md = readme_md.replace("APP_NAME", APP_NAME)
            readme_md = readme_md.replace("REPO_CLONE_URL", REPO_CLONE_URL)
            readme_md_b64 = b64encode(readme_md.encode("utf-8")).decode("utf-8")
            data = {
                "message": "create README.md",
                "committer": {"name": username, "email": email},
                "content": readme_md_b64,
            }
            req = requests.put(
                f"https://api.github.com/repos/{git_org}/{repo_name}/contents/README.md",
                headers=headers,
                data=json.dumps(data),
            )

    # Create docker-compose.yml github workflow
    with open("./repo-template-files/docker-compose.yml") as fp:
        docker_compose_yml = fp.read()
        docker_compose_yml = docker_compose_yml.replace("APP_NAME", APP_NAME)
        docker_compose_yml_b64 = b64encode(docker_compose_yml.encode("utf-8")).decode(
            "utf-8"
        )
        data = {
            "message": "create .docker-compose.yml",
            "committer": {"name": username, "email": email},
            "content": docker_compose_yml_b64,
        }
        req = requests.put(
            f"https://api.github.com/repos/{git_org}/{repo_name}/contents/docker-compose.yml",
            headers=headers,
            data=json.dumps(data),
        )

    # Create SQL/"newSQL" database for container
    try:
        req = requests.post("https://db.anotherwebservice.com/?json=1")
        db_settings = req.json()
        DB_HOST = db_settings["hostname"]
        DB_PORT = db_settings["port"]
        DB_NAME = db_settings["db_name"]
        DB_USER = db_settings["username"]
        DB_PASSWORD = db_settings["password"]

    except Exception as e:
        print(f"Error getting db settings {e}")

    # Create framework quickstart if requested
    """
    1. Clone their repo (the one we just created for them)
    2. git add framework quickstart files
    3. commit
    3. push
    """
    # Clone their repo we just created
    repo = Repo.clone_from(
        f"https://{access_token}@github.com/{git_org}/{repo_name}.git",
        f"./tmp-cloned-repos/{APP_NAME}",
    )
    repo.config_writer().set_value("user", "name", username).release()
    repo.config_writer().set_value("user", "email", email).release()

    # Setup secrets using amber
    amber_secret_key = subprocess.run(
        "amber init 2> /dev/null| sed 's/export AMBER_SECRET=//g'",
        shell=True,
        capture_output=True,
        cwd=f"./tmp-cloned-repos/{APP_NAME}",
    )
    AMBER_SECRET = amber_secret_key.stdout.strip().decode("utf-8")
    # POST AMBER_SECRET to DOKKU_HOST_SSH_ENDPOINT
    data = {
        "CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY": CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY,
        "APP_NAME": APP_NAME,
        "KEY": f"{APP_NAME}:AMBER_SECRET",
        "VALUE": AMBER_SECRET,
    }
    try:
        print("Posting to DOKKU_HOST_SSH_ENDPOINT")
        req = requests.post(
            DOKKU_HOST_SSH_ENDPOINT + "/STORE-KEY-VALUE", json=data, timeout=10
        )
    except requests.exceptions.ConnectTimeout as e:
        print(f"Ignoring ConnectTimeout because we fire and forget: {e}")

    print("POST GIT_USERNAME_OR_ORG to DOKKU_HOST_SSH_ENDPOINT STORE-KEY-VALUE")
    KEY = f"{APP_NAME}:GIT_USERNAME_OR_ORG"
    data = {
        "CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY": CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY,
        "APP_NAME": APP_NAME,
        "KEY": KEY,
        "VALUE": git_org,  # git_org contains username if not an org
    }
    try:
        print("Posting GIT_USERNAME_OR_ORG to DOKKU_HOST_SSH_ENDPOINT")
        req = requests.post(
            DOKKU_HOST_SSH_ENDPOINT + "/STORE-KEY-VALUE", json=data, timeout=10
        )
    except requests.exceptions.ConnectTimeout as e:
        print(f"Ignoring ConnectTimeout because we fire and forget: {e}")

    print("POST GIT_REPO_NAME to DOKKU_HOST_SSH_ENDPOINT STORE-KEY-VALUE")
    KEY = f"{APP_NAME}:GIT_REPO_NAME"
    data = {
        "CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY": CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY,
        "APP_NAME": APP_NAME,
        "KEY": KEY,
        "VALUE": repo_name,
    }
    try:
        print("Posting GIT_REPO_NAME to DOKKU_HOST_SSH_ENDPOINT")
        req = requests.post(
            DOKKU_HOST_SSH_ENDPOINT + "/STORE-KEY-VALUE", json=data, timeout=10
        )
    except requests.exceptions.ConnectTimeout as e:
        print(f"Ignoring ConnectTimeout because we fire and forget: {e}")

    # Store AMBER_SECRET in github secrets (this is the (only?) secret which
    # needs to be stored in the CI/CD provider (Github) secrets tool.
    github_store_secret("AMBER_SECRET", AMBER_SECRET)

    # Store CONTAINER_HOSTING_API_KEY in amber.yaml
    amber_encrypt(
        "CONTAINER_HOSTING_API_KEY",
        CONTAINER_HOSTING_API_KEY,
        amber_file_location=amber_file_location,
    )

    amber_encrypt("DOKKU_HOST", DOKKU_HOST, amber_file_location=amber_file_location)
    amber_encrypt(
        "SSH_CONFIG_FILE", "/dev/null", amber_file_location=amber_file_location
    )
    amber_encrypt(
        "RUNNING_WITHIN_CI_PIPELINE", "1", amber_file_location=amber_file_location
    )
    amber_encrypt(
        "GIT_USERNAME_OR_ORG", git_org, amber_file_location=amber_file_location
    )
    amber_encrypt("GIT_REPO_NAME", repo_name, amber_file_location=amber_file_location)

    # Set common ENV settings across all framworks/apps
    amber_encrypt("DB_USER", DB_USER, amber_file_location=amber_file_location)
    amber_encrypt("DB_PASSWORD", DB_PASSWORD, amber_file_location=amber_file_location)
    amber_encrypt("DB_HOST", DB_HOST, amber_file_location=amber_file_location)
    amber_encrypt("DB_PORT", DB_PORT, amber_file_location=amber_file_location)
    amber_encrypt("DB_NAME", DB_NAME, amber_file_location=amber_file_location)
    amber_encrypt(
        "ALLOWED_HOSTS",
        f"{APP_NAME}.containers.anotherwebservice.com",
        amber_file_location=amber_file_location,
    )

    # Note we prepend the word "RAILS" but when used, rails
    # needs the ENV variable name to be DATABASE_URL
    RAILS_DATABASE_URL = (
        f"mysql2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}?pool=5"
    )
    amber_encrypt(
        "RAILS_DATABASE_URL",
        RAILS_DATABASE_URL,
        amber_file_location=amber_file_location,
    )

    DJANGO_ALLOWED_HOSTS = app_host
    amber_encrypt(
        "DJANGO_ALLOWED_HOSTS",
        DJANGO_ALLOWED_HOSTS,
        amber_file_location=amber_file_location,
    )

    DJANGO_SECRET_KEY = secrets.token_urlsafe(30)
    amber_encrypt(
        "DJANGO_SECRET_KEY", DJANGO_SECRET_KEY, amber_file_location=amber_file_location
    )

    DJANGO_DEBUG = "True"
    amber_encrypt("DJANGO_DEBUG", DJANGO_DEBUG, amber_file_location=amber_file_location)

    DJANGO_ENGINE = "django.db.backends.mysql"
    amber_encrypt(
        "DJANGO_ENGINE", DJANGO_ENGINE, amber_file_location=amber_file_location
    )

    DJANGO_DB_HOST = DB_HOST
    amber_encrypt(
        "DJANGO_DB_HOST", DJANGO_DB_HOST, amber_file_location=amber_file_location
    )

    DJANGO_DB_NAME = DB_NAME
    amber_encrypt(
        "DJANGO_DB_NAME", DJANGO_DB_NAME, amber_file_location=amber_file_location
    )

    DJANGO_DB_USER = DB_USER
    amber_encrypt(
        "DJANGO_DB_USER", DJANGO_DB_USER, amber_file_location=amber_file_location
    )

    DJANGO_DB_PASSWORD = DB_PASSWORD
    amber_encrypt(
        "DJANGO_DB_PASSWORD",
        DJANGO_DB_PASSWORD,
        amber_file_location=amber_file_location,
    )

    DJANGO_DB_PORT = DB_PORT
    amber_encrypt(
        "DJANGO_DB_PORT", DJANGO_DB_PORT, amber_file_location=amber_file_location
    )

    def add_flask_quickstart():
        # add framework quickstart files
        shutil.copytree(
            f"{BASE_PATH}/repo-template-files/quickstarts/flask-quickstart/src",
            f"./tmp-cloned-repos/{APP_NAME}/src",
            dirs_exist_ok=True,
        )
        # add/commit framework files to repo
        index = repo.index
        index.add([f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/src/web"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/src/entrypoint.sh"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/src/Dockerfile"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/src/requirements.txt"])
        index.commit("Added flask quickstart")

    if "rails" in state:
        # add framework quickstart files
        shutil.copytree(
            f"{BASE_PATH}/repo-template-files/quickstarts/rails-quickstart/src",
            f"./tmp-cloned-repos/{repo_name}/src",
            dirs_exist_ok=True,
        )
        # add/commit framework files to repo
        index = repo.index
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/app"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/entrypoint.sh"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/Dockerfile"])
        index.commit("Added rails quickstart")

    if "django" in state:
        # add framework quickstart files
        shutil.copytree(
            f"{BASE_PATH}/repo-template-files/quickstarts/django-quickstart/src",
            f"./tmp-cloned-repos/{repo_name}/src",
            dirs_exist_ok=True,
        )
        # add/commit framework files to repo
        index = repo.index
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/web"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/entrypoint.sh"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/Dockerfile"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/requirements.txt"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/wait-for.sh"])
        index.commit("Added django quickstart")

    if "flask" in state:
        add_flask_quickstart()

    if "---existing_repo-" in state:
        # In this case don't create a new repo, only
        # add to the existing repo provided in ---existing_repo-.. metadata
        # example state:
        # mT4D4deeuV7VJDiYwMHZ_9Wk2DTZYEgUKvyzgEzD---existing_repo-github.com|KarmaComputing|container-hosting
        # which we split into unsafe_git_host, unsafe_git_org, unsafe_repo_name
        unsafe_git_host, unsafe_git_org, unsafe_repo_name = state.split(
            "---existing_repo-"
        )[1].split("|")

        # If existing repo, default to adding flask quickstart
        add_flask_quickstart()

        # Update repo homepage url
        data = {
            "homepage": app_url,
        }
        req = requests.patch(
            f"https://api.github.com/repos/{git_org}/{repo_name}",
            headers=headers,
            data=json.dumps(data),
        )
        print(req.json())

    # git push the repo
    origin = repo.remotes[0]
    repo.heads.main.set_tracking_branch(origin.refs.main)
    fetch = origin.fetch()[0]
    log.info(fetch)

    # Commit amber.yaml secrets file to repo
    index = repo.index
    index.add([f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/amber.yaml"])
    index.commit("Added amber.yaml secrets file")

    # Setup .autorc
    fp = open("./repo-template-files/.autorc")
    autorc = fp.read()
    autorc = autorc.replace("GITHUB_OWNER", git_org)
    autorc = autorc.replace("GITHUB_REPO_NAME", repo_name)
    autorc = autorc.replace("GITHUB_EMAIL", email)
    fp.close()
    with open(f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.autorc", "w") as fp:
        fp.write(autorc)

    index = repo.index
    index.add([f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.autorc"])
    index.commit("Added .autorc file")

    # Create deploy.sh in .container-hosting/deploy.sh
    os.makedirs(
        f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.container-hosting", exist_ok=True
    )
    fp = open("./repo-template-files/.container-hosting/deploy.sh")
    deploy_sh = fp.read()
    fp.close()

    with open(
        f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.container-hosting/deploy.sh",
        "w",
    ) as fp:
        fp.write(deploy_sh)

    # Mark deploy.sh execute bit
    f = Path(f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.container-hosting/deploy.sh")
    f.chmod(f.stat().st_mode | stat.S_IEXEC)

    index = repo.index
    index.add([f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.container-hosting/deploy.sh"])
    index.commit("Added deploy.sh file")

    # Create release.yml github workflow
    fp = open("./repo-template-files/.github/workflows/release.yml")
    release_yml = fp.read()
    fp.close()
    os.makedirs(
        f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.github/workflows/", exist_ok=True
    )
    with open(
        f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.github/workflows/release.yml", "w"
    ) as fp:
        fp.write(release_yml)

    index = repo.index
    index.add([f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.github/workflows/release.yml"])
    index.commit("Added release.yml file")

    # Create deploy.yml github workflow (last action- triggers first deploy pipeline)
    fp = open("./repo-template-files/.github/workflows/deploy.yml")
    deploy_yml = fp.read()
    fp.close()
    with open(
        f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.github/workflows/deploy.yml", "w"
    ) as fp:
        deploy_yml = deploy_yml.replace("$APP_NAME", APP_NAME)
        deploy_yml = deploy_yml.replace("$GIT_USERNAME_OR_ORG", git_org)
        deploy_yml = deploy_yml.replace("$GIT_REPO_NAME", repo_name)
        fp.write(deploy_yml)

    index.add([f"{BASE_PATH}tmp-cloned-repos/{APP_NAME}/.github/workflows/deploy.yml"])
    index.commit("Added deploy.yml file")

    push = origin.push()[0]
    print(push.summary)

    # Signal that a new repo is created
    signal_new_repo.send(
        {
            "app_url": app_url,
            "APP_NAME": APP_NAME,
            "repo_name": repo_name,
            "user_email": email,
            "avatar_url": avatar_url,
            "github_username": username,
            "github_repo_origin": origin,
            "AMBER_SECRET": AMBER_SECRET,
        }
    )

    return templates.TemplateResponse(
        "welcome.html", {"repo_url": repo_url, "request": request}
    )


async def blog(request):
    return templates.TemplateResponse("heroku-alternatives.html", {"request": request})


async def health(request):
    log.debug(request)
    return PlainTextResponse("OK")


async def notify(request):
    log.info(request)
    return PlainTextResponse("Notification sent")


async def not_found(request: Request, exc: HTTPException):
    return HTMLResponse(content="404", status_code=exc.status_code)


async def server_error(request: Request, exc: HTTPException):
    return HTMLResponse(content="500", status_code=500)


async def catch_all(request: Request):
    return templates.TemplateResponse(
        f"{request.path_params['path']}.html", {"request": request}
    )


async def robots(request: Request):
    return PlainTextResponse("user-agent: *")


routes = [
    Route("/", homepage, methods=["GET", "POST"]),
    Route("/robots.txt", robots),
    Route("/health", health, methods=["GET"]),
    Route("/githubcallback", githubcallback, methods=["GET"]),
    Route("/heroku-alternatives", blog, methods=["GET"]),
    Route("/notify", notify, methods=["GET"]),
    Mount("/static", app=StaticFiles(directory="static"), name="static"),
    Route("/{path:path}", catch_all),
]

exception_handlers = {404: not_found, 500: server_error}

app = Starlette(debug=False, routes=routes, exception_handlers=exception_handlers)
