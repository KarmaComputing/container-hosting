#!/bin/bash

REPO_NAME=$1
GITHUB_OWNER=$2

set -x
set -e
#create repo inside a username
curl \
  -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/user/repos \
  -d '{"name":"'"$REPO_NAME"'","homepage":"'"https://github.com/$GITHUB_OWNER/$REPO_NAME"'","private":false,"has_issues":true,"has_projects":true,"has_wiki":true}'
##getting the public key and KEY_ID
KEY_ID=`./repo-key.sh $REPO_NAME $GITHUB_OWNER $TOKEN | grep "key_id" | cut -d '"' -f4`
REPO_PUBLIC_KEY=`./repo-key.sh $REPO_NAME $GITHUB_OWNER $TOKEN | grep '"key"' | cut -d '"' -f4`

#SSH_PRIVATE_KEY=`cat ~/.ssh/id_rsa`

##getting the encrypted part out of the python script
DOKKU_DOMAIN_ENCRYPTED=`python3 encrypt.py $DOKKU_DOMAIN $REPO_PUBLIC_KEY`
DOKKU_HOST_ENCRYPTED=`python3 encrypt.py $DOKKU_HOST $REPO_PUBLIC_KEY`
SSH_PRIVATE_KEY_ENCRYPTED=`python3 encrypt.py $SSH_PRIVATE_KEY $REPO_PUBLIC_KEY`

mkdir -p repositories/$REPO_NAME
cp -r clone-repo-files/.github ./repositories/$REPO_NAME
cp clone-repo-files/.autorc ./repositories/$REPO_NAME
cp clone-repo-files/README.md ./repositories/$REPO_NAME
#Getting inside the new github repo
cd repositories/$REPO_NAME
git init
#Using template + sed to change the values
sed -i "s/REPO_NAME/$REPO_NAME/g" .autorc
sed -i "s/GITHUB_OWNER/$GITHUB_OWNER/g" .autorc
sed -i "s/REPO_NAME/$REPO_NAME/g" .github/workflows/*
sed -i "s/GITHUB_OWNER/$GITHUB_OWNER/g" .github/workflows/*

#commit
git add .
git commit -m "initial commit"
git branch -M main
git remote add origin git@github.com:$GITHUB_OWNER/$REPO_NAME.git || true

#create the secrets inside github repo
curl \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/$GITHUB_OWNER/$REPO_NAME/actions/secrets/DOKKU_DOMAIN \
  -d '{"encrypted_value":"'"$DOKKU_DOMAIN_ENCRYPTED"'","key_id":"'"$KEY_ID"'"}'
curl \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/$GITHUB_OWNER/$REPO_NAME/actions/secrets/DOKKU_HOST \
  -d '{"encrypted_value":"'"$DOKKU_HOST_ENCRYPTED"'","key_id":"'"$KEY_ID"'"}'
curl \
  -X PUT \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: token $TOKEN" \
  https://api.github.com/repos/$GITHUB_OWNER/$REPO_NAME/actions/secrets/SSH_PRIVATE_KEY \
  -d '{"encrypted_value":"'"$SSH_PRIVATE_KEY_ENCRYPTED"'","key_id":"'"$KEY_ID"'"}'

#push to the repo
git push -u origin main
