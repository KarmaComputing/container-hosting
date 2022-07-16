#!/bin/bash

#uvicorn app:app --host 0.0.0.0 --port 443 --ssl-keyfile=/path-to/privkey.pem --ssl-certfile=/path-to/fullchain.pem --reload
uvicorn app:app --host 0.0.0.0 --port 5000 --reload

