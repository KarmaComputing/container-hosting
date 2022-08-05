from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, Mount
from starlette.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles

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

load_dotenv(verbose=True)

templates = Jinja2Templates(directory="templates")

BASE_PATH = os.getenv("BASE_PATH")
GITHUB_OAUTH_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID")
GITHUB_OAUTH_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI")
DOKKU_HOST = os.getenv("DOKKU_HOST")
DOKKU_HOST_SSH_ENDPOINT = os.getenv("DOKKU_HOST_SSH_ENDPOINT")

# See https://github.com/dokku/dokku-letsencrypt/pull/211


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
    public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
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
    github_authorize_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&state={state}&scope=repo%20user:email"  # noqa: E501
    github_authorize_url_rails = f"https://github.com/login/oauth/authorize?client_id={client_id}&state={state_rails}&scope=repo%20user:email"  # noqa: E501
    github_authorize_url_django = f"https://github.com/login/oauth/authorize?client_id={client_id}&state={state_django}&scope=repo%20user:email"  # noqa: E501

    return templates.TemplateResponse(
        "index.html",
        {
            "github_authorize_url": github_authorize_url,
            "github_authorize_url_rails": github_authorize_url_rails,
            "github_authorize_url_django": github_authorize_url_django,
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
        "https://github.com/login/oauth/access_token", data=data, headers=headers
    )

    # Get access token from github
    resp = req.json()
    access_token = resp.get("access_token")
    scope = resp.get("scope")
    print(access_token)

    # Use access token
    headers = {"Authorization": f"token {access_token}"}
    headers["Accept"] = "application/vnd.github+json"
    # Create api key for container-hosting
    CONTAINER_HOSTING_API_KEY = f"secret_{secrets.token_urlsafe(60)}"
    # Create unique repo name
    random_string = secrets.token_urlsafe(5).lower().replace("_", "")
    app_host = f"container-{random_string}.containers.anotherwebservice.com"
    app_url = f"https://container-{random_string}.containers.anotherwebservice.com/"
    repo_name = f"container-{random_string}"
    data = {
        "name": repo_name,
        "description": "Created using https://container-hosting.anotherwebservice.com/#start",
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

    # Upload initial repo content
    with open("./repo-template-files/.autorc") as fp:
        autorc = fp.read()
        autorc = autorc.replace("GITHUB_OWNER", username)
        autorc = autorc.replace("GITHUB_REPO_NAME", repo_name)
        autorc_b64 = b64encode(autorc.encode("utf-8")).decode("utf-8")
        data = {
            "message": "create .autorc",
            "committer": {"name": username, "email": email},
            "content": autorc_b64,
        }
        req = requests.put(
            f"https://api.github.com/repos/{username}/{repo_name}/contents/.autorc",
            headers=headers,
            data=json.dumps(data),
        )

    # Upload initial Dockerfile
    with open("./repo-template-files/src/Dockerfile") as fp:
        dockerfile = fp.read()
        dockerfile = dockerfile.replace("GITHUB_OWNER", username)
        dockerfile = dockerfile.replace("GITHUB_REPO_NAME", repo_name)
        dockerfile_b64 = b64encode(dockerfile.encode("utf-8")).decode("utf-8")
        data = {
            "message": "create .dockerfile",
            "committer": {"name": username, "email": email},
            "content": dockerfile_b64,
        }
        req = requests.put(
            f"https://api.github.com/repos/{username}/{repo_name}/contents/src/Dockerfile",
            headers=headers,
            data=json.dumps(data),
        )

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
    public_key = f'no-agent-forwarding,no-user-rc,no-X11-forwarding,no-port-forwarding {public_key.decode("utf-8")}'
    # POST public key to DOKKU_HOST_SSH_ENDPOINT
    data = {"public_key": public_key}
    req = requests.post(DOKKU_HOST_SSH_ENDPOINT, json=data)
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

    # Set Repo Secret DOKKU_HOST
    github_store_secret("DOKKU_HOST", DOKKU_HOST)

    # Create README.md
    REPO_CLONE_URL = f"git@github.com:{username}/{repo_name}.git"
    with open("./repo-template-files/README.md") as fp:
        readme_md = fp.read()
        readme_md = readme_md.replace("APP_URL", app_url)
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

    # Create release.yml github workflow
    with open("./repo-template-files/.github/workflows/release.yml") as fp:
        release_yml = fp.read()
        release_yml = release_yml.replace("GITHUB_OWNER", username)
        release_yml = release_yml.replace("GITHUB_REPO_NAME", repo_name)
        release_yml_b64 = b64encode(release_yml.encode("utf-8")).decode("utf-8")
        data = {
            "message": "create .release_yml",
            "committer": {"name": username, "email": email},
            "content": release_yml_b64,
        }
        req = requests.put(
            f"https://api.github.com/repos/{username}/{repo_name}/contents/.github/workflows/release.yml",
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
        db_hostname = db_settings["hostname"]
        db_port = db_settings["port"]
        db_name = db_settings["db_name"]
        db_username = db_settings["username"]
        db_password = db_settings["password"]

        # Note we prepend the word "RAILS" but when used, rails
        # needs the ENV variable name to be DATABASE_URL
        RAILS_DATABASE_URL = f"mysql2://{db_username}:{db_password}@{db_hostname}:{db_port}/{db_name}?pool=5"
        github_store_secret("RAILS_DATABASE_URL", RAILS_DATABASE_URL)

        DJANGO_ALLOWED_HOSTS = app_host
        github_store_secret("DJANGO_ALLOWED_HOSTS", app_host)
        DJANGO_SECRET_KEY = secrets.token_urlsafe(30)
        github_store_secret("DJANGO_SECRET_KEY", DJANGO_SECRET_KEY)
        DJANGO_DEBUG = "True"
        github_store_secret("DJANGO_DEBUG", DJANGO_DEBUG)
        DJANGO_ENGINE = "django.db.backends.mysql"
        github_store_secret("DJANGO_ENGINE", DJANGO_ENGINE)
        DJANGO_DB_HOST = db_hostname
        github_store_secret("DJANGO_DB_HOST", DJANGO_DB_HOST)
        DJANGO_DB_NAME = db_name
        github_store_secret("DJANGO_DB_NAME", DJANGO_DB_NAME)
        DJANGO_DB_USER = db_username
        github_store_secret("DJANGO_DB_USER", DJANGO_DB_USER)
        DJANGO_DB_PASSWORD = db_password
        github_store_secret("DJANGO_DB_PASSWORD", DJANGO_DB_PASSWORD)
        DJANGO_DB_PORT = db_port
        github_store_secret("DJANGO_DB_PORT", DJANGO_DB_PORT)
    except Exception as e:
        print(f"Error getting db settings {e}")

    # Create framework quickstart if requested
    """
    1. Clone their repo (the one we just created for them)
    2. git add framework quickstart files
    3. commit
    3. push
    """
    if "rails" in state:
        # Clone their repo we just created
        repo = Repo.clone_from(
            f"https://{access_token}@github.com/{username}/{repo_name}.git",
            f"./tmp-cloned-repos/{repo_name}",
        )
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
        # git push framework quickstart to repo
        origin = repo.remotes[0]
        repo.heads.main.set_tracking_branch(origin.refs.main)
        push = origin.push()[0]
        print(push.summary)

    if "django" in state:
        # Clone their repo we just created
        repo = Repo.clone_from(
            f"https://{access_token}@github.com/{username}/{repo_name}.git",
            f"./tmp-cloned-repos/{repo_name}",
        )
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
        # git push framework quickstart to repo
        origin = repo.remotes[0]
        repo.heads.main.set_tracking_branch(origin.refs.main)
        push = origin.push()[0]
        print(push.summary)

    # Create deploy.yml github workflow
    with open("./repo-template-files/.github/workflows/deploy.yml") as fp:
        deploy_yml = fp.read()
        deploy_yml = deploy_yml.replace("GITHUB_OWNER", username)
        # APP_NAME is for dokku, and is currently the same as
        # the REPO_NAME.
        deploy_yml = deploy_yml.replace("APP_NAME", repo_name)
        deploy_yml = deploy_yml.replace("REPO_NAME", repo_name)
        deploy_yml = deploy_yml.replace("DJANGO_ALLOWED_HOSTS", DJANGO_ALLOWED_HOSTS)
        deploy_yml_b64 = b64encode(deploy_yml.encode("utf-8")).decode("utf-8")
        data = {
            "message": "create deploy.yml",
            "committer": {"name": username, "email": email},
            "content": deploy_yml_b64,
        }
        req = requests.put(
            f"https://api.github.com/repos/{username}/{repo_name}/contents/.github/workflows/deploy.yml",
            headers=headers,
            data=json.dumps(data),
        )

    # Get the deploy workflow id
    import time

    time.sleep(3)  # TODO hook/poll
    req = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}/actions/workflows",
        headers=headers,
    )
    deploy_workflow_id = req.json()["workflows"][0]["id"]
    # Start the deploy.yml workflow action
    data = {"ref": "main"}

    req = requests.post(
        f"https://api.github.com/repos/{username}/{repo_name}/actions/workflows/{deploy_workflow_id}/dispatches",
        headers=headers,
        data=json.dumps(data),
    )

    return templates.TemplateResponse(
        "welcome.html", {"repo_url": repo_url, "request": request}
    )


async def health(request):
    print(request)
    return PlainTextResponse("OK")


routes = [
    Route("/", homepage, methods=["GET", "POST"]),
    Route("/health", health, methods=["GET"]),
    Route("/githubcallback", githubcallback, methods=["GET"]),
]

app = Starlette(debug=True, routes=routes)
