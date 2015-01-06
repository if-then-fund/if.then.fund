#!/bin/bash

# Check that the environment file exists.
if [ ! -f local/environment.json ]; then
	echo "Missing: local/environment.json"
	exit 1
fi

# DEPLOYED TO WEB ONLY
if [ "$1" == "--deployed" ]; then
	git config --global user.name "Joshua Tauberer"
	git config --global user.email jt@occams.info
	git config --global push.default simple

	sudo apt-get update -q -q && sudo apt-get upgrade
fi

# Get remote libraries.

git submodule update --init

mkdir -p itfsite/static/js/ext
wget -qO itfsite/static/js/ext/jquery.payment.js https://raw.githubusercontent.com/stripe/jquery.payment/3dbada6a8c7fbb0d13ac121d0581a738d9576f53/lib/jquery.payment.js

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
		echo Need to install: $TO_INSTALL
		sudo DEBIAN_FRONTEND=noninteractive sudo apt-get -y install $PACKAGES
	fi
}

apt_install python3 python-virtualenv python3-pip python3-dnspython python3-yaml python3-lxml python3-dateutil

# DEPLOYED TO WEB ONLY
if [ "$1" == "--deployed" ]; then
	# Get nginx from a PPA to get version 1.6 so we can support SPDY.
	if [ ! -f /etc/apt/sources.list.d/nginx-stable-trusty.list ]; then
		sudo apt_install software-properties-common # provides apt-add-repository
		sudo add-apt-repository -y ppa:nginx/stable
		sudo apt-get update
	fi

	# Install nginx, uwsgi, memcached etc.
	apt_install nginx uwsgi-plugin-python3 memcached python3-psycopg2 postgresql-client-9.3

	# Turn off nginx's default website.
	sudo rm -f /etc/nginx/sites-enabled/default

	# Put in our site.
	sudo rm -f /etc/nginx/sites-enabled/ifthenfund.conf /etc/nginx/nginx-ssl.conf
	sudo ln -s `pwd`/conf/nginx.conf /etc/nginx/sites-enabled/ifthenfund.conf
	sudo ln -s `pwd`/conf/nginx-ssl.conf /etc/nginx/nginx-ssl.conf

	# DHparams for perfect forward secrecy
	if [ ! -f /etc/ssl/local/dh2048.pem ]; then
		mkdir -p /etc/ssl/local
		sudo openssl dhparam -out /etc/ssl/local/dh2048.pem 2048
	fi

	# Fetch AWS's CA for its RDS postgres database certificates.
	# Use sslmode=verify-full and sslrootcert=/etc/ssl/certs/rds-ssl-ca-cert.pem
	sudo wget -O /etc/ssl/certs/rds-ssl-ca-cert.pem https://rds.amazonaws.com/doc/rds-ssl-ca-cert.pem

	# A place to collect static files and to serve as the virtual root.
	mkdir -p /home/ubuntu/public_html/static
	sudo service nginx restart

	# Execute pip as root because the uwsgi process starter doesn't
	# work (at least not obviously so) with a virtualenv.
	easy_install3 pip # http://stackoverflow.com/questions/27341064/how-do-i-fix-importerror-cannot-import-name-incompleteread
	PIP="sudo pip3"
fi

# LOCAL ONLY
if [ "$1" == "--local" ]; then
	# Create the Python virtual environment for pip package installation.
	# We use --system-site-packages to make it easier to get dependencies
	# via apt first.
	if [ ! -d .env ]; then
		virtualenv -p python3 --system-site-packages .env
	fi
	
	# Activate virtual environment.
	source .env/bin/activate

	# How shall we execute pip.
	PIP="pip -q"
fi

# Install dependencies.
$PIP install --upgrade \
	"rtyaml" \
	"django>=1.7.1" \
	"python3-memcached" \
	"requests" \
	"markdown2" \
	"jsonfield" \
	"tqdm==1.0" \
	"enum3field"

$PIP install --upgrade -r \
	ext/django-email-confirm-la/requirements.txt

# Required by django-html-emailer. Need to get Python 3 fork.
$PIP install git+https://github.com/dcramer/pynliner@python3

# LOCAL ONLY
if [ "$1" == "--local" ]; then
	# Create database / migrate database.
	./manage.py makemigrations itfsite contrib
	./manage.py migrate

	# Create an 'admin' user.
	./manage.py createsuperuser --email=ops@if.then.fund --noinput 2&> /dev/null
	# gain access with: ./manage.py changepassword ops@if.then.fund

	# Load fixtures. Only for testing...
	./manage.py loaddata fixtures/actors.json
fi

# DEPLOYED TO WEB ONLY
if [ "$1" == "--deployed" ]; then
	python3 manage.py collectstatic --noinput
fi
