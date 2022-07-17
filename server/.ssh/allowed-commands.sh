#!/bin/sh

# Only allow these commands

case "$SSH_ORIGINAL_COMMAND" in
    "ls")
        ls
        ;;
    "dokku builder:set APP_NAME build-dir src")
        dokku builder:set REPO_NAME build-dir src
        ;;
    "dokku builder-dockerfile:set APP_NAME dockerfile-path Dockerfile")
        dokku builder-dockerfile:set APP_NAME dockerfile-path Dockerfile
        ;;
    "dokku git:sync --build minimalcd https://github.com/GITHUB_OWNER/APP_NAME.git main")
        dokku git:sync --build minimalcd https://github.com/GITHUB_OWNER/APP_NAME.git main
        ;;
    *)
        echo "Access denied"
        exit 1
        ;;
esac

