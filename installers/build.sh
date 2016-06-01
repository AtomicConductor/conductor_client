#!/bin/bash -ex
curl -s -o python.tgz "https://www.python.org/ftp/python/2.7.11/Python-2.7.11.tgz"
tar zxf python.tgz

./windows/build.sh
./osx/build.sh
./rpm/build.sh
./debian/build.sh