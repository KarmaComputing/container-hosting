from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.responses import HTMLResponse
from starlette.requests import Request


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

    See also https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/
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
    body = await request.body()
    print(body)

    client_id = GITHUB_OAUTH_CLIENT_ID
    state = f"{secrets.token_urlsafe(30)}---no-framework"
    state_rails = f"{secrets.token_urlsafe(30)}---rails"
    state_django = f"{secrets.token_urlsafe(30)}---django"
    state_flask = f"{secrets.token_urlsafe(30)}---flask"
    github_authorize_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&state={state}&scope=workflow%20repo%20user:email"  # noqa: E501
    github_authorize_url_rails = f"https://github.com/login/oauth/authorize?client_id={client_id}&state={state_rails}&scope=workflow%20repo%20user:email"  # noqa: E501
    github_authorize_url_django = f"https://github.com/login/oauth/authorize?client_id={client_id}&state={state_django}&scope=workflow%20repo%20user:email"  # noqa: E501
    github_authorize_url_flask = f"https://github.com/login/oauth/authorize?client_id={client_id}&state={state_flask}&scope=workflow%20repo%20user:email"  # noqa: E501

    return templates.TemplateResponse(
        "index.html",
        {
            "github_authorize_url": github_authorize_url,
            "github_authorize_url_rails": github_authorize_url_rails,
            "github_authorize_url_django": github_authorize_url_django,
            "github_authorize_url_flask": github_authorize_url_flask,
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
    # Create api key for container-hosting
    CONTAINER_HOSTING_API_KEY = f"secret_{secrets.token_urlsafe(60)}"
    # Create unique repo name
    random_string = secrets.token_urlsafe(5).lower().replace("_", "")
    app_host = f"container-{random_string}.containers.anotherwebservice.com"
    app_url = f"https://container-{random_string}.containers.anotherwebservice.com/"  # noqa: E501
    repo_name = f"container-{random_string}"
    os.makedirs(f"./tmp-cloned-repos/{repo_name}", exist_ok=True)
    amber_file_location = f"./tmp-cloned-repos/{repo_name}/amber.yaml"

    data = {
        "name": repo_name,
        "description": "Created using https://container-hosting.anotherwebservice.com/#start",  # noqa: E501
        "homepage": app_url,
        "private": False,
        "has_issues": True,
        "has_projects": True,
        "has_wiki": True,
    }
    req = requests.get("https://api.github.com/user", headers=headers).json()
    # Get their GitHub username
    username = req.get("login")
    avatar_url = req.get("avatar_url")
    print(f"avatar_url: {avatar_url}")
    # Get email address so can do git commits with correct author information
    req = requests.get("https://api.github.com/user/emails", headers=headers)
    email = req.json()[0].get("email", None)

    # Create a repo for organisation user has access to
    # req = requests.post("https://api.github.com/orgs/karmacomputing/repos", headers=headers, data=json.dumps(data))
    # Create repo for authenticated user
    req = requests.post(
        "https://api.github.com/user/repos", headers=headers, data=json.dumps(data)
    )
    repo_url = req.json()["html_url"]
    print(repo_url)

    # Create repo secrets
    req = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}/actions/secrets/public-key",
        headers=headers,
    ).json()
    github_repo_public_key = req["key"]
    github_repo_public_key_id = req["key_id"]

    def github_store_secret(SECRET_NAME, SECRET_VALUE: str):
        secret_Encrypted = encrypt_github_secret(github_repo_public_key, SECRET_VALUE)
        data = {
            "encrypted_value": secret_Encrypted,
            "key_id": github_repo_public_key_id,
        }
        req = requests.put(
            f"https://api.github.com/repos/{username}/{repo_name}/actions/secrets/{SECRET_NAME}",
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
        "APP_NAME": repo_name,
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
        f"https://api.github.com/repos/{username}/{repo_name}/actions/secrets/DOKKU_SSH_PRIVATE_KEY",
        headers=headers,
        data=json.dumps(data),
    )

    # Create README.md
    REPO_CLONE_URL = f"git@github.com:{username}/{repo_name}.git"
    with open("./repo-template-files/README.md") as fp:
        readme_md = fp.read()
        readme_md = readme_md.replace("APP_URL", app_url)
        readme_md = readme_md.replace("APP_NAME", repo_name)
        readme_md = readme_md.replace("REPO_CLONE_URL", REPO_CLONE_URL)
        readme_md_b64 = b64encode(readme_md.encode("utf-8")).decode("utf-8")
        data = {
            "message": "create README.md",
            "committer": {"name": username, "email": email},
            "content": readme_md_b64,
        }
        req = requests.put(
            f"https://api.github.com/repos/{username}/{repo_name}/contents/README.md",
            headers=headers,
            data=json.dumps(data),
        )

    # Create docker-compose.yml github workflow
    with open("./repo-template-files/docker-compose.yml") as fp:
        docker_compose_yml = fp.read()
        docker_compose_yml = docker_compose_yml.replace("APP_NAME", repo_name)
        docker_compose_yml_b64 = b64encode(docker_compose_yml.encode("utf-8")).decode(
            "utf-8"
        )
        data = {
            "message": "create .docker-compose.yml",
            "committer": {"name": username, "email": email},
            "content": docker_compose_yml_b64,
        }
        req = requests.put(
            f"https://api.github.com/repos/{username}/{repo_name}/contents/docker-compose.yml",
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
        f"https://{access_token}@github.com/{username}/{repo_name}.git",
        f"./tmp-cloned-repos/{repo_name}",
    )
    repo.config_writer().set_value("user", "name", username).release()
    repo.config_writer().set_value("user", "email", email).release()

    # Setup secrets using amber
    amber_secret_key = subprocess.run(
        "amber init 2> /dev/null| sed 's/export AMBER_SECRET=//g'",
        shell=True,
        capture_output=True,
        cwd=f"./tmp-cloned-repos/{repo_name}",
    )
    AMBER_SECRET = amber_secret_key.stdout.strip().decode("utf-8")
    # POST AMBER_SECRET to DOKKU_HOST_SSH_ENDPOINT
    data = {
        "CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY": CONTAINER_HOSTING_SSH_SETUP_HANDLER_API_KEY,
        "APP_NAME": repo_name,
        "KEY": f"{repo_name}:AMBER_SECRET",
        "VALUE": AMBER_SECRET,
    }
    try:
        print("Posting to DOKKU_HOST_SSH_ENDPOINT")
        req = requests.post(
            DOKKU_HOST_SSH_ENDPOINT + "/STORE-KEY-VALUE", json=data, timeout=0.001
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

    # Set common ENV settings across all framworks/apps
    amber_encrypt("DB_USER", DB_USER, amber_file_location=amber_file_location)
    amber_encrypt("DB_PASSWORD", DB_PASSWORD, amber_file_location=amber_file_location)
    amber_encrypt("DB_HOST", DB_HOST, amber_file_location=amber_file_location)
    amber_encrypt("DB_PORT", DB_PORT, amber_file_location=amber_file_location)
    amber_encrypt("DB_NAME", DB_NAME, amber_file_location=amber_file_location)

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
        # add framework quickstart files
        shutil.copytree(
            f"{BASE_PATH}/repo-template-files/quickstarts/flask-quickstart/src",
            f"./tmp-cloned-repos/{repo_name}/src",
            dirs_exist_ok=True,
        )
        # add/commit framework files to repo
        index = repo.index
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/web"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/entrypoint.sh"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/Dockerfile"])
        index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/src/requirements.txt"])
        index.commit("Added flask quickstart")

    # git push the repo
    origin = repo.remotes[0]
    repo.heads.main.set_tracking_branch(origin.refs.main)
    fetch = origin.fetch()[0]

    # Commit amber.yaml secrets file to repo
    index = repo.index
    index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/amber.yaml"])
    index.commit("Added amber.yaml secrets file")

    # Setup .autorc
    fp = open("./repo-template-files/.autorc")
    autorc = fp.read()
    autorc = autorc.replace("GITHUB_OWNER", username)
    autorc = autorc.replace("GITHUB_REPO_NAME", repo_name)
    fp.close()
    with open(f"{BASE_PATH}tmp-cloned-repos/{repo_name}/.autorc", "w") as fp:
        fp.write(autorc)

    index = repo.index
    index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/.autorc"])
    index.commit("Added .autorc file")

    # Create release.yml github workflow
    fp = open("./repo-template-files/.github/workflows/release.yml")
    release_yml = fp.read()
    fp.close()
    os.makedirs(
        f"{BASE_PATH}tmp-cloned-repos/{repo_name}/.github/workflows/", exist_ok=True
    )
    with open(
        f"{BASE_PATH}tmp-cloned-repos/{repo_name}/.github/workflows/release.yml", "w"
    ) as fp:
        fp.write(release_yml)

    index = repo.index
    index.add(
        [f"{BASE_PATH}tmp-cloned-repos/{repo_name}/.github/workflows/release.yml"]
    )
    index.commit("Added release.yml file")

    # Create deploy.yml github workflow (last action- triggers first deploy pipeline)
    fp = open("./repo-template-files/.github/workflows/deploy.yml")
    deploy_yml = fp.read()
    fp.close()
    with open(
        f"{BASE_PATH}tmp-cloned-repos/{repo_name}/.github/workflows/deploy.yml", "w"
    ) as fp:
        deploy_yml = deploy_yml.replace("GITHUB_OWNER", username)
        # APP_NAME is for dokku, and is currently the same as
        # the REPO_NAME.
        deploy_yml = deploy_yml.replace("APP_NAME", repo_name)
        deploy_yml = deploy_yml.replace("REPO_NAME", repo_name)
        fp.write(deploy_yml)

    index.add([f"{BASE_PATH}tmp-cloned-repos/{repo_name}/.github/workflows/deploy.yml"])
    index.commit("Added deploy.yml file")

    push = origin.push()[0]
    print(push.summary)

    return templates.TemplateResponse(
        "welcome.html", {"repo_url": repo_url, "request": request}
    )


async def blog(request):
    return templates.TemplateResponse("heroku-alternatives.html", {"request": request})


async def health(request):
    print(request)
    return PlainTextResponse("OK")


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
    Route("/{path:path}", catch_all),
]

exception_handlers = {404: not_found, 500: server_error}

app = Starlette(debug=False, routes=routes, exception_handlers=exception_handlers)
