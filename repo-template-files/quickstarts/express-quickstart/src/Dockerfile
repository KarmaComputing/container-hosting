FROM node:20-alpine

WORKDIR /app/src
COPY . /app/src

RUN npm install

RUN chown -R node:node /app

USER node

ENTRYPOINT /app/src/entrypoint.sh
