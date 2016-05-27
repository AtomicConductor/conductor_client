#!/bin/bash -ex
export RELEASE_VERSION=$(python -c "import os,json;print json.loads(os.environ['payload'])['release']['tag_name']")
git clone https://github.com/AtomicConductor/conductor_client.git

curl -s -o python.tgz "https://www.python.org/ftp/python/2.7.11/Python-2.7.11.tgz"
tar zxf python.tgz

pushd conductor_client
git checkout tags/${RELEASE_VERSION}
sed -i "s/#__version__=\"0.0.0\"/__version__=\"${RELEASE_VERSION}\"/" \
    conductor/__init__.py
echo $payload > conductor/release.json

./installers/windows/build.sh
./installers/osx/build.sh
./installers/rpm/build.sh
./installers/debian/build.sh

UPLOAD_URL=$(python -c "import os,json;print json.loads(os.environ['payload'])['release']['upload_url'][:-13]")
curl -s -u ${GITHUB_API_TOKEN} --data-binary @installers/windows/conductor-${RELEASE_VERSION}.exe -H "Content-Type:application/octet-stream" "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}.exe"
curl -s -u ${GITHUB_API_TOKEN} --data-binary @installers/osx/conductor-${RELEASE_VERSION}.pkg -H "Content-Type:application/octet-stream" "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}.pkg"
curl -s -u ${GITHUB_API_TOKEN} --data-binary @installers/rpm/conductor-${RELEASE_VERSION}-0.noarch.rpm -H "Content-Type:application/octet-stream" "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}-0.noarch.rpm"
curl -s -u ${GITHUB_API_TOKEN} --data-binary @installers/debian/conductor_${RELEASE_VERSION:1}.deb -H "Content-Type:application/octet-stream" "${UPLOAD_URL}?name=conductor_${RELEASE_VERSION:1}.deb"