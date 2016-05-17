#!/bin/bash
apt-get update && \
apt-get install -y --allow-unauthenticated \
                build-essential \
                libsqlite3-dev \
                libssl-dev \
                libbz2-dev \
                libgdbm-dev \
                libncurses5-dev \
                libreadline-dev \
                libdb-dev \
                tk-dev \
                curl
                

<<<<<<< HEAD
<<<<<<< HEAD
/root/src/configure --prefix=/root/python && make && make install
curl -O "https://bootstrap.pypa.io/get-pip.py"
/root/python/bin/python get-pip.py
/root/python/bin/pip install pyaml requests urllib3
=======
cd /root
mkdir build python
cd build
/tmp/Python*/configure --prefix=/root/python && make && make install
curl -O "https://bootstrap.pypa.io/get-pip.py"
../python/bin/python get-pip.py

../python/bin/pip install pyaml requests urllib3
>>>>>>> 4fcd197... dynamic python build
=======
/root/src/configure --prefix=/root/python && make && make install
curl -O "https://bootstrap.pypa.io/get-pip.py"
/root/python/bin/python get-pip.py
/root/python/bin/pip install pyaml requests urllib3
>>>>>>> 5154e12... fix rpm uploads
