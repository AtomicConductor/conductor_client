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

sleep 600
/root/src/configure --prefix=/root/python && make && make install
curl -O "https://bootstrap.pypa.io/get-pip.py"
/root/python/bin/python get-pip.py
/root/python/bin/pip install pyaml requests urllib3
