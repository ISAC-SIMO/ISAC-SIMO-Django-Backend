#!/bin/bash
# Change to your app directory
cd /root/isac/ISAC-SIMO_Django/
echo '==PULLING FROM MASTER=='
git pull origin master

source env/bin/activate
pip install -r requirements.txt

# python manage.py clearsessions
python manage.py migrate
echo '==MIGRATE AND PULL DONE=='

deactivate

# FOR PYTHON ANYWHERE
# touch /var/www/buildchange_pythonanywhere_com_wsgi.py
#touch /var/www/www_isac-simo_net_wsgi.py
#echo '==REQUESTED RELOAD=='

echo '==RESTARTING=='
systemctl restart nginx
systemctl restart gunicorn
echo '==DONE=='

# Notes Theano:
# 1. If Theano fails in server, download conda in server to use Theano Backend (use wget and bash)
# 2. Theano requires g++ from c++ compiler along with conda stuffs
# 3. For local download MinGW and install g++ along with conda stuffs

# Windows: http://deeplearning.net/software/theano/install_windows.html
# Ubuntu: http://deeplearning.net/software/theano/install_ubuntu.html
# CentOS: http://deeplearning.net/software/theano/install_centos6.html