#! /usr/bin/python3.8
import sys
import subprocess
import sqlite3
import json

api_key_to_container = {}

# Example mapping between secret api keys to container app names
"""
api_key_to_container = {
    "secret_ffdb467952c9309403dc94c59729f9275d82d59ce635b2dc2b07dcc32a95": {
        "APP_NAME": "container-id1bklk",
        "APP_URL": "container-id1bklk.containers.anotherwebservice.com",
        "RAILS_DEVELOPMENT_HOSTS": "container-id1bklk.containers.anotherwebservice.com",
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

for row in cur.execute('SELECT * FROM container'):
    container = json.loads(row[0])
    api_key_to_container[[*container.keys()][0]] = container[[*container.keys()][0]]


print("In dokku-wrapper.py")

unsafe_api_key = sys.argv[1]
print(f"Checking unsafe_api_key: {unsafe_api_key}")


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
    "git-sync": "dokku git:sync --build APP_NAME https://github.com/GITHUB_USERNAME/APP_NAME.git main",
    "certs-add": "dokku certs:add APP_NAME < cert-key.tar",
    "set-env-RAILS_DEVELOPMENT_HOSTS": "dokku config:set --no-restart APP_NAME RAILS_DEVELOPMENT_HOSTS=APP_URL",
    "set-env-DATABASE_URL": "dokku config:set --no-restart APP_NAME DATABASE_URL=RAILS_DATABASE_URL",
    "set-env-SECRET_KEY": "dokku config:set --no-restart APP_NAME SECRET_KEY=DJANGO_SECRET_KEY",
    "set-env-ALLOWED_HOSTS": "dokku config:set --no-restart APP_NAME ALLOWED_HOSTS='APP_URL'",
    "set-env-DEBUG": "dokku config:set --no-restart APP_NAME DEBUG=DJANGO_DEBUG",
    "set-env-DJANGO_ENGINE":"dokku config:set --no-restart APP_NAME DB_ENGINE=DJANGO_ENGINE",
    "set-env-DJANGO_DB_NAME": "dokku config:set --no-restart APP_NAME DB_NAME=DJANGO_DB_NAME",
    "set-env-DJANGO_DB_HOST": "dokku config:set --no-restart APP_NAME DB_HOST=DJANGO_DB_HOST",
    "set-env-DJANGO_DB_USER": "dokku config:set --no-restart APP_NAME DB_USER=DJANGO_DB_USER",
    "set-env-DJANGO_DB_PASSWORD": "dokku config:set --no-restart APP_NAME DB_PASSWORD=DJANGO_DB_PASSWORD",
    "set-env-DJANGO_DB_PORT": "dokku config:set --no-restart APP_NAME DB_PORT=DJANGO_DB_PORT",
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
