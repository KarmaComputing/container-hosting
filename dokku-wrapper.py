#! /usr/bin/python3.8
import sys
import subprocess
import json

print("In dokku-wrapper.py")

unsafe_api_key = sys.argv[1]
print(f"Checking unsafe_api_key: {unsafe_api_key}")

# Mapping between secret api keys to container app names
with open("api_key_to_container.json") as fp:
    api_key_to_container = json.loads(fp.read())
    """
    Example datastructure: api_key_to_container.json 
    api_key_to_container = {
        "secret_ffdb467952c9309403dc94c59729f9275d82d59ce635b2dc2b07dcc32a95": {
            "APP_NAME": "container-abc123",
            "APP_URL": "container-abc123.containers.anotherwebservice.com",
            "RAILS_DEVELOPMENT_HOSTS": "container-abc123.containers.anotherwebservice.com",
            "RAILS_DATABASE_URL": "",
            "DJANGO_SECRET_KEY":"",
            "ALLOWED_HOSTS":"",
            "DEBUG": "",
        }
    }
    """

try:
    APP_NAME = api_key_to_container[unsafe_api_key]
except KeyError as e:
    print("Invalid api key")
    exit()

print("Valid api key")
APP_NAME = api_key_to_container[unsafe_api_key]['APP_NAME']
print(f"app_name: {APP_NAME}")

unsafe_requested_command = sys.argv[2]

commands_allowlist = {
    "app-create": "dokku apps:create APP_NAME",
    "set-docker-build-dir": "dokku builder:set APP_NAME build-dir src",
    "set-docker-Dockerfile-path": "dokku builder-dockerfile:set APP_NAME dockerfile-path Dockerfile",
    "set-env-RAILS_DEVELOPMENT_HOSTS": "dokku config:set --no-restart APP_NAME RAILS_DEVELOPMENT_HOSTS=APP_URL",
    "set-env-DATABASE_URL": "dokku config:set --no-restart APP_NAME DATABASE_URL=RAILS_DATABASE_URL",
    "set-env-SECRET_KEY": "dokku config:set --no-restart APP_NAME SECRET_KEY=DJANGO_SECRET_KEY",
    "set-env-ALLOWED_HOSTS": "dokku config:set --no-restart APP_NAME ALLOWED_HOSTS='APP_URL'",
    "set-env DEBUG": "dokku config:set --no-restart APP_NAME DEBUG=DJANGO_DEBUG",
}

if unsafe_requested_command not in commands_allowlist:
    print("Invalid command. Possible commands are:")
    for command_example in commands_allowlist.keys():
        print(command_example)
    exit()
else:
    print("Valid command")
    safer_command = commands_allowlist[unsafe_requested_command].replace(
        "APP_NAME", APP_NAME
    )
    print(f"Safer command: {safer_command}")
    print("Running command")
    subprocess.run(safer_command, shell=True)
