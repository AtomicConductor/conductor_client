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
                

/root/src/configure --prefix=/root/python && make && make install
curl -O "https://bootstrap.pypa.io/get-pip.py"
/root/python/bin/python get-pip.py
/root/python/bin/pip install pyaml requests urllib3