#!/bin/bash -ex
curl -s -o python.tgz "https://www.python.org/ftp/python/2.7.11/Python-2.7.11.tgz"
tar zxf python.tgz

sed -i "s/#__version__=\"0.0.0\"/__version__=\"${RELEASE_VERSION}\"/" \
    conductor/__init__.py
echo $payload > conductor/release.json

./windows/build.sh
./osx/build.sh
./rpm/build.sh
./debian/build.sh