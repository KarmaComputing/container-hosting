#!/bin/sh
set -ex

/wait-for.sh db-host.anotherwebservice.com:4000 --timeout=60 -- python manage.py runserver 0.0.0.0:5000
