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
<<<<<<< HEAD
<<<<<<< HEAD


/root/src/configure --prefix=/root/python && make && make install
curl -O "https://bootstrap.pypa.io/get-pip.py"
/root/python/bin/python get-pip.py
/root/python/bin/pip install pyaml requests urllib3
=======
               
=======

<<<<<<< HEAD
sleep 600
>>>>>>> f4ffdb7... debug docker paths
/root/src/configure --prefix=/root/python && make && make install
curl -O "https://bootstrap.pypa.io/get-pip.py"
<<<<<<< HEAD
../python/bin/python get-pip.py

../python/bin/pip install pyaml requests urllib3
>>>>>>> 4fcd197... dynamic python build
=======
/root/python/python/bin/python get-pip.py
/root/python/python/bin/pip install pyaml requests urllib3
>>>>>>> 777c3b9... python build
=======

/root/src/configure --prefix=/root/python && make && make install
curl -O "https://bootstrap.pypa.io/get-pip.py"
/root/python/bin/python get-pip.py
/root/python/bin/pip install pyaml requests urllib3
>>>>>>> 70b650d... fix docker paths
