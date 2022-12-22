FROM python:alpine

EXPOSE 5000

WORKDIR /usr/src/app

RUN adduser -D -H -u 10000 app app

COPY requirements.txt ./
RUN apk add git
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

USER app

ENTRYPOINT /usr/src/app/entrypoint.sh

