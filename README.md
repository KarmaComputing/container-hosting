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
pip install -r -U requirements.txt
./run.sh
```

## Adding ssh keys to dokku server(s)

Read https://dokku.com/docs/deployment/user-management/#:~:text=format%20json%20admin-,Adding%20SSH%20keys,-You%20can%20add
