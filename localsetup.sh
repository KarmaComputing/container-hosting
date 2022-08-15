#!/bin/bash

set -ex

python3 -m venv venv
. venv/bin/activate

pip install -r requirements.txt

echo Done
