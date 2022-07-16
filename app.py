from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route, Mount
from starlette.templating import Jinja2Templates
from starlette.staticfiles import StaticFiles
import os
import requests
import json
from uuid6 import uuid7
import base64

import secrets
from dotenv import load_dotenv

load_dotenv(verbose=True)

templates = Jinja2Templates(directory="templates")

GITHUB_OAUTH_CLIENT_ID = os.getenv("GITHUB_OAUTH_CLIENT_ID")
GITHUB_OAUTH_CLIENT_SECRET = os.getenv("GITHUB_OAUTH_CLIENT_SECRET")
GITHUB_OAUTH_REDIRECT_URI = os.getenv("GITHUB_OAUTH_REDIRECT_URI")


async def homepage(request):
    """Homepage and display connect Github link"""
    body = await request.body()
    print(body)

    client_id = GITHUB_OAUTH_CLIENT_ID
    state = secrets.token_urlsafe(30)
    github_authorize_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&state={state}&scope=repo%20user:email"  # noqa: E501

    return templates.TemplateResponse(
        "index.html", {"github_authorize_url": github_authorize_url, "request": request}
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
    # Create unique repo name
    uuid = uuid7()
    repo_name = f"container-hosting-{uuid}"
    data = {
        "name": repo_name,
        "description": "This is your first repository",
        "homepage": "https://container-hosting.anotherwebservice.com/",
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
        autorc_b64 = base64.b64encode(autorc.encode("utf-8")).decode("utf-8")
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
    with open("./repo-template-files/.github/workflows/release.yml") as fp:
        release_yml = fp.read()
        release_yml = release_yml.replace("GITHUB_OWNER", username)
        release_yml = release_yml.replace("GITHUB_REPO_NAME", repo_name)
        release_yml_b64 = base64.b64encode(release_yml.encode("utf-8")).decode("utf-8")
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
