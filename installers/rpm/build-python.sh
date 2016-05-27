#!/bin/bash
yum groupinstall -y "Development Tools"
yum install -y sqlite-devel \
               gdbm-devel \
               openssl-devel \
               ncurses-devel \
               readline-devel \
               bzip2-devel \
               db4-devel \
               tk-devel \
               libdb-devel
               
cd /root
mkdir build python
cd build
/tmp/Python*/configure --prefix=/root/python && make && make install
curl -O "https://bootstrap.pypa.io/get-pip.py"
../python/bin/python get-pip.py

../python/bin/pip install pyaml requests urllib3
