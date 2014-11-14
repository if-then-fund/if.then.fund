#!/bin/bash

# Install package dependencies.

function apt_install {
	# Check which packages are already installed before attempting to
	# install them. Avoids the need to sudo, which makes testing easier.
	PACKAGES=$@
	TO_INSTALL=""
	for pkg in $PACKAGES; do
		if ! dpkg -s $pkg 2>/dev/null | grep "^Status: install ok installed" > /dev/null; then
			TO_INSTALL="$TO_INSTALL""$pkg "
		fi
	done

	if [[ ! -z "$TO_INSTALL" ]]; then
		DEBIAN_FRONTEND=noninteractive sudo apt-get -y install $PACKAGES
	fi
}

apt_install python3-dnspython

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
	"requests" \
	"markdown2" \
	"jsonfield" \
	"enum3field"

# Get remote libraries.
wget -qO itfsite/static/js/ext/jquery.payment.js https://raw.githubusercontent.com/stripe/jquery.payment/3dbada6a8c7fbb0d13ac121d0581a738d9576f53/lib/jquery.payment.js

if [ ! -d twostream ]; then
	git clone https://github.com/govtrack/twostream
fi

# Create database / migrate database.
./manage.py makemigrations itfsite contrib
./manage.py migrate

# Create an 'admin' user which will own all of the triggers, if the
# user doesn't already exist.
./manage.py createsuperuser --email=admin@unnamedsite.com --noinput 2&> /dev/null
# gain access with: ./manage.py changepassword admin
