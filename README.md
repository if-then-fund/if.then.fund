if.then.fund
============

The source code for the website https://if.then.fund by Civic Responsibility, LLC.

We are making this repository publicly accessible because we think it's the right thing to do.

We don't expect anyone to run this code. The instructions below are for us.

Deployment
----------

Spin up an Ubuntu 14.04 LTS 64-bit machine. Log in and run:

	sudo apt-get update && sudo apt-get upgrade -y
	sudo apt-get install -y git
	git clone --recursive https://github.com/if-then-fund/if.then.fund
	cd if.then.fund

Create:

	local/environment.json
	/etc/ssl/local/ssl_certificate.crt
	/etc/ssl/local/ssl_certificate.key
    
For a local, testing environment ('runserver', new sqlite database):

	./bootstrap.sh --local

For a (pre-)production environment (nginx, existing database):

	./bootstrap.sh --deployed

For a new database, initialize data:

	./manage.py create_actors
