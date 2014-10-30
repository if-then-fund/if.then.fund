#!/bin/bash

# Create the Python virtual environment for pip package installation.
# We ues --system-site-packages to take advantage of Ubuntu security
# updates.
if [ ! -d .env ]; then
	virtualenv -p python3 --system-site-packages .env
fi

# Activate virtual environment.
source .env/bin/activate

# Install dependencies.
pip install --upgrade \
	"django>=1.7.1" \
	"markdown2" \
	"jsonfield" \
	"enum3field"

# Get remote libraries.
wget -O itfsite/static/js/ext/jquery.payment.js https://raw.githubusercontent.com/stripe/jquery.payment/3dbada6a8c7fbb0d13ac121d0581a738d9576f53/lib/jquery.payment.js

# Create database / migrate database.
./manage.py migrate

# Create an 'admin' user which will own all of the triggers, if the
# user doesn't already exist.
./manage.py createsuperuser --username=admin --email=admin@unnamedsite.com --noinput 2&> /dev/null
# gain access with: ./manage.py changepassword admin
