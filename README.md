## This repo automatically creates a new repository with the following features in your Github account:
* auto release versions
* code analytics
* issues template
* repository secrets creation 
* dokku pr-previews and deployment workflows
* deletion of the dokku pr-previews after merge.

## Run locally

```
python3 -m venv venv
. venv/bin/activate
cp .env.example .env
pip install -r requirements.txt -U
./run.sh
```
Change the .env file with the correct settings. 

First register a new Oauth application to get the following 3 variable values: 
```GITHUB_OAUTH_CLIENT_ID```, ```GITHUB_OAUTH_CLIENT_SECRET```, ```GITHUB_OAUTH_REDIRECT_URI```

https://github.com/settings/applications/new

If you are running dokku on a remote server remember to put your public key into the server's authorized_keys file.
 
## Adding ssh keys to dokku server(s)

Read https://dokku.com/docs/deployment/user-management/#:~:text=format%20json%20admin-,Adding%20SSH%20keys,-You%20can%20add

## Additional Information

Dokku provides an integration with Caddy proxy which is installed if docker-compose-plugin is installed.
For this case, we will need to remove Caddy proxy since it uses port 80 and cause port conflicts with nginx
To remove Caddy simple run ```dokku caddy:stop```
