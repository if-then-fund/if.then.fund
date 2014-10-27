#!/bin/bash

# Create the Python virtual environment for pip package installation.
# We ues --system-site-packages to take advantage of Ubuntu security
# updates.
if [ ! -d .env ]; then
	virtualenv -p python3 --system-site-packages .env
fi

. .env/bin/activate

pip install --upgrade \
	"django>=1.7.1" \
	"jsonfield" \
	"enum3field"

