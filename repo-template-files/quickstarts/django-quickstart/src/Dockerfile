# syntax=docker/dockerfile:1
FROM python:3-alpine
ENV PYTHONUNBUFFERED=1
RUN apk update && apk add --no-cache build-base mariadb-dev netcat-openbsd encodings
WORKDIR /usr/src/app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY ./web .
COPY ./entrypoint.sh /
COPY ./wait-for.sh /
ENTRYPOINT ["/entrypoint.sh"]
