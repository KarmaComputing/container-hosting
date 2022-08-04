#! /usr/bin/python3.8
import sys
import subprocess
import sqlite3
import json

print("In dokku-wrapper.py")

#https://github.com/pyca/pynacl/issues/192

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



unsafe_api_key = sys.argv[1]
print(f"Checking unsafe_api_key: {unsafe_api_key}")


try:
    APP_NAME = api_key_to_container[unsafe_api_key]
except KeyError as e:
    print("Invalid api key")
    exit()

print("Valid api key")

try:
    APP_NAME = api_key_to_container[unsafe_api_key]['APP_NAME']
    GITHUB_USERNAME = api_key_to_container[unsafe_api_key]["GITHUB_USERNAME"]
    print(f"app_name: {APP_NAME}")
except KeyError as e:
    print(f"Error getting app setting: {e}")
    exit()

unsafe_requested_command = ''
MAX_ARGS=7
if len(sys.argv) > MAX_ARGS:
    print(f"Too many args. Got {len(sys.argv)} expected {MAX_ARGS}")
    exit()

for arg in sys.argv[2:MAX_ARGS]:
    unsafe_requested_command += f"{arg} "
unsafe_requested_command = unsafe_requested_command.strip()

commands_allowlist = [
    "dokku apps:create APP_NAME",
    "dokku builder:set APP_NAME build-dir src",
    "dokku builder-dockerfile:set APP_NAME dockerfile-path Dockerfile",
    "dokku git:sync --build APP_NAME https://github.com/GITHUB_USERNAME/APP_NAME.git main",
    "dokku certs:add APP_NAME < cert-key.tar",
    "dokku config:set --no-restart APP_NAME RAILS_DEVELOPMENT_HOSTS=APP_URL",
    "dokku config:set --no-restart APP_NAME DATABASE_URL=RAILS_DATABASE_URL",
    "dokku config:set --no-restart APP_NAME SECRET_KEY=DJANGO_SECRET_KEY",
    "dokku config:set --no-restart APP_NAME ALLOWED_HOSTS='APP_URL'",
    "dokku config:set --no-restart APP_NAME DEBUG=DJANGO_DEBUG",
    "dokku config:set --no-restart APP_NAME DB_ENGINE=DJANGO_ENGINE",
    "dokku config:set --no-restart APP_NAME DB_NAME=DJANGO_DB_NAME",
    "dokku config:set --no-restart APP_NAME DB_HOST=DJANGO_DB_HOST",
    "dokku config:set --no-restart APP_NAME DB_USER=DJANGO_DB_USER",
    "dokku config:set --no-restart APP_NAME DB_PASSWORD=DJANGO_DB_PASSWORD",
    "dokku config:set --no-restart APP_NAME DB_PORT=DJANGO_DB_PORT",
    ]

valid_command = False

for allowed_command in commands_allowlist:
    allowed_command = allowed_command.replace("APP_NAME", APP_NAME).replace("GITHUB_USERNAME", GITHUB_USERNAME)
    print(f"Comparing: {allowed_command} with {unsafe_requested_command}")
    if allowed_command ==  unsafe_requested_command:
        valid_command = True
        break;

if valid_command is False:
    print("Invalid command. Possible commands are:")
    for possible_command in commands_allowlist:
        print(possible_command.replace("APP_NAME", APP_NAME).replace("GITHUB_USERNAME", GITHUB_USERNAME))
    exit()
else:
    print("Valid command")
    print(f"Allowed command: {allowed_command}")
    print("Running command")
    subprocess.run(allowed_command, shell=True)
