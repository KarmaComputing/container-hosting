#!/bin/sh
set -ex

exec /wait-for.sh $DB_HOST:$DB_PORT --timeout=60 -- sh -c 'python manage.py migrate && python /usr/src/app/manage.py runserver 0.0.0.0:5000'
