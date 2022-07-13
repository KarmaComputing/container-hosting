#!/bin/bash

REPO_NAME=$1
GITHUB_OWNER=$2
TOKEN=$3
curl \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/$GITHUB_OWNER/$REPO_NAME/actions/secrets/public-key

