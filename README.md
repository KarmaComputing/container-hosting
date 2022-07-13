## This repo automatically creates a new repository with the following features in your Github account:
* auto release versions
* code analytics
* issues template
* repository secrets creation 
* dokku pr-previews and deployment workflows
* deletion of the dokku pr-previews after merge.

## Run locally

1. [Install rust](https://rustup.rs/)
2. Run web app:
```
cd container-hosting
cargo run
```

## To start creating first create a token (PAT)</br>
https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token

Then you will need to fill the .env.example with the required information. </br>

```
python3 -m venv venv
pip install -r requirements.txt
cp .env.example .env
export $(grep -v '^#' .env | xargs) #export all .env variables
chmod +x auto-repo.sh
chmod +x repo-key.sh
```
```
./auto-repo.sh <repo-name> <github-owner>
```

You will need a folder structure of 
```
<repo-name>/src/Dockerfile
```
after the first commit is being pushed to enable the pr-preview and deploy workflows</br>

### Enjoy your new repo!

# Web
