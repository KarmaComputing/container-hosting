#! /usr/bin/python3.8
import subprocess
import sqlite3
import json
import os
import logging
import shlex

print("🐧 In dokku-wrapper.py")
# print(os.getenv("SSH_ORIGINAL_COMMAND"))

unsafe_SSH_ORIGINAL_COMMAND = os.getenv("SSH_ORIGINAL_COMMAND")
unsafe_api_key = str(unsafe_SSH_ORIGINAL_COMMAND[0:87])

# https://github.com/pyca/pynacl/issues/192

CERTIFICATE_WILDCARD_BUNDLE_PATH = os.getenv("CERTIFICATE_WILDCARD_BUNDLE_PATH")


unsafe_requested_command = unsafe_SSH_ORIGINAL_COMMAND[88:]
MAX_LENGTH = 700
if len(unsafe_requested_command) > MAX_LENGTH:
    print(
        f"Command too long. Got: {len(unsafe_requested_command)}. MAX_LENGTH: {MAX_LENGTH}"
    )
    exit()

api_key_to_container = {}
# Example mapping between secret api keys to container app names
"""
api_key_to_container = {
    "secret_ffdb467952c9309403dc94c59729f9275d82d59ce635b2dc2b07dcc32a95": {
        "APP_NAME": "container-okt2ri4",
        "APP_URL": "container-okt2ri4.containers.anotherwebservice.com",
        "RAILS_DEVELOPMENT_HOSTS": "container-okt2ri4.containers.anotherwebservice.com",
        "RAILS_DATABASE_URL": "",
        "DJANGO_SECRET_KEY":"",
        "ALLOWED_HOSTS":"",
        "DEBUG": "",
        "DJANGO_ENGINE": "",
        "DJANGO_DB_NAME": "",
        "DJANGO_DB_HOST": "",
        "DJANGO_DB_USER": "",
        "DJANGO_DB_PASSWORD": "",
        "GITHUB_USERNAME": ""
    }
}
"""
con = sqlite3.connect("containers.db")
cur = con.cursor()

cur.execute(
    "SELECT * FROM container WHERE CONTAINER_HOSTING_API_KEY = ?", (unsafe_api_key,)
)

APP_FOUND = False
for row in cur.fetchall():
    try:
        container = json.loads(row[0])
        APP_NAME = container["APP_NAME"]
        CONTAINER_HOSTING_API_KEY = row[1]
        APP_FOUND = True

    except json.decoder.JSONDecodeError as e:
        logging.error(f"json.decoder.JSONDecodeError: {e}")

if APP_FOUND is False:
    logging.error("Unable to find app")
    print("Unable to find app, perhaps your CONTAINER_HOSTING_API_KEY is wrong?")
    exit()

print(f"🐌 Limiting app CPU resources for app: {APP_NAME}")
subprocess.run(f"dokku resource:limit --cpu 1.5 {APP_NAME}", shell=True)

print(f"🧠 Limiting app memory resources for app: {APP_NAME}")
subprocess.run(f"dokku resource:limit --memory 500m {APP_NAME}", shell=True)


try:
    print(f"✅ Located APP_NAME: {APP_NAME}")
except KeyError as e:
    print(f"Error getting app setting: {e}")
    exit()

print("🔓 Valid api key")

print("👀 Getting GIT_USERNAME_OR_ORG")

con = sqlite3.connect("key_value_store.db")
cur = con.cursor()

cur.execute(
    f"select * from key_value_store WHERE key = '{APP_NAME}:GIT_USERNAME_OR_ORG'"
)

FOUND_GIT_USERNAME_OR_ORG = False
for row in cur.fetchall():
    try:
        GIT_USERNAME_OR_ORG = row[1]
        logging.info(
            f"Found GIT_USERNAME_OR_ORG: {GIT_USERNAME_OR_ORG} for container {row[0]}"
        )
        FOUND_GIT_USERNAME_OR_ORG = True

    except (IndexError, Exception) as e:
        logging.error(f"Could not locate GIT_USERNAME_OR_ORG: {e}")

if FOUND_GIT_USERNAME_OR_ORG is False:
    logging.error("Unable to find GIT_USERNAME_OR_ORG")
    print(
        "Unable to find GIT_USERNAME_OR_ORG, perhaps your CONTAINER_HOSTING_API_KEY is wrong?"
    )
    exit()


print("✅ Matched GIT_USERNAME_OR_ORG")


print("👀 Getting GIT_REPO_NAME")

cur.execute(f"select * from key_value_store WHERE key = '{APP_NAME}:GIT_REPO_NAME'")

FOUND_GIT_REPO_NAME = False
for row in cur.fetchall():
    try:
        GIT_REPO_NAME = row[1]
        logging.info(f"Found GIT_REPO_NAME: {GIT_REPO_NAME} for container {row[0]}")
        FOUND_GIT_REPO_NAME = True

    except (IndexError, Exception) as e:
        logging.error(f"Could not locate GIT_REPO_NAME: {e}")

if FOUND_GIT_REPO_NAME is False:
    logging.error("Unable to find GIT_REPO_NAME")
    print(
        "Unable to find GIT_REPO_NAME, perhaps your CONTAINER_HOSTING_API_KEY is wrong?"
    )
    exit()


print("✅ Matched GIT_REPO_NAME")


# dokku config:set --no-restart container-fjxt9w4 ALLOWED_HOSTS=container-fjxt9w4.containers.anotherwebservice.com

commands_allowlist = [
    "dokku apps:create APP_NAME",
    "dokku builder:set APP_NAME build-dir src",
    "dokku builder-dockerfile:set APP_NAME dockerfile-path Dockerfile",
    "dokku git:sync --build APP_NAME https://github.com/GITHUB_USERNAME/APP_NAME.git main",
    "dokku certs:add APP_NAME < cert-key.tar",
    "dokku config:set --no-restart APP_NAME RAILS_DEVELOPMENT_HOSTS=APP_URL",
    "dokku config:set --no-restart APP_NAME DATABASE_URL=RAILS_DATABASE_URL",
    "dokku config:set --no-restart APP_NAME SECRET_KEY=DJANGO_SECRET_KEY",
    "dokku config:set --no-restart APP_NAME ALLOWED_HOSTS=APP_NAME.containers.anotherwebservice.com",
    "dokku config:set APP_NAME ALLOWED_HOSTS=APP_NAME.containers.anotherwebservice.com",
    "dokku config:set --no-restart APP_NAME DEBUG=DJANGO_DEBUG",
    "dokku config:set --no-restart APP_NAME DB_ENGINE=DJANGO_ENGINE",
    "dokku config:set --no-restart APP_NAME DB_NAME=DJANGO_DB_NAME",
    "dokku config:set --no-restart APP_NAME DB_HOST=DJANGO_DB_HOST",
    "dokku config:set --no-restart APP_NAME DB_USER=DJANGO_DB_USER",
    "dokku config:set --no-restart APP_NAME DB_PASSWORD=DJANGO_DB_PASSWORD",
    "dokku config:set --no-restart APP_NAME DB_PORT=DJANGO_DB_PORT",
    "dokku logs APP_NAME",
]

valid_command = False

possible_commands = []
for allowed_command in commands_allowlist:
    possible_commands.append(allowed_command.replace("APP_NAME", APP_NAME))

del os.environ["SSH_ORIGINAL_COMMAND"]
if unsafe_requested_command in possible_commands:
    valid_command = True
    print("✅ Valid command")
    print(f"✅ Allowed command: {unsafe_requested_command}")
    # del SSH_ORIGINAL_COMMAND from environ otherwise
    # otherwise arg $1 which is CONTAINER_HOSTING_API_KEY gets passed to
    # dokku src:
    # https://github.com/dokku/dokku/blob/6a3933213c70a142587418bcf84835c832b09feb/dokku#L118

    # Get final_command from commands_allowlist -> possible_commands
    final_command = possible_commands[possible_commands.index(unsafe_requested_command)]
    # See https://docs.python.org/3/library/subprocess.html#security-considerations

    final_command = shlex.split(final_command)
    print(f"⏳ Running: {final_command}")
    subprocess.run(final_command)
    print("✨ Completed run")

elif "config:set" in unsafe_requested_command:
    # TODO IMPROVE THIS NOT IDEAL SECURITY
    valid_command = True
    unsafe_command = shlex.split(
        f'dokku config:set --no-restart {APP_NAME} {unsafe_requested_command.split(f"{APP_NAME}")[1].strip()}'
    )

    print(f"⏳ Running: {unsafe_command}")
    subprocess.run(unsafe_command)
    print("✨ Completed run")

if "cert-key.tar" in unsafe_requested_command:
    # TODO IMPROVE THIS NOT IDEAL SECURITY
    valid_command = True
    print(
        f"⏳ Running: dokku certs:add '{APP_NAME}' < $CERTIFICATE_WILDCARD_BUNDLE_PATHcert-key.tar"
    )
    subprocess.run(
        f"dokku certs:add '{APP_NAME}' < {CERTIFICATE_WILDCARD_BUNDLE_PATH}cert-key.tar",
        shell=True,
    )
    print("✨ Completed run")


if "dokku git:sync" in unsafe_requested_command:
    # TODO IMPROVE THIS NOT IDEAL SECURITY
    valid_command = True
    unsafe_command = shlex.split(
        f"dokku git:sync --build {APP_NAME} https://github.com/{GIT_USERNAME_OR_ORG}/{GIT_REPO_NAME}.git main"
    )

    print(f"⏳ Running: {unsafe_command}")
    subprocess.run(unsafe_command)
    print("✨ Completed run")

    # Rebuild app
    print(f"⏳ Rebuilding app: {APP_NAME}")
    subprocess.run(shlex.split(f"dokku ps:rebuild {APP_NAME}"))


if valid_command is False:
    print(f"Invalid command: {unsafe_requested_command}. \nPossible commands are:")
    for possible_command in commands_allowlist:
        print(possible_command.replace("APP_NAME", APP_NAME))
    exit()
