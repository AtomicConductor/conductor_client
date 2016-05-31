#!/bin/bash -x
pushd $( dirname "${BASH_SOURCE[0]}" )

VERSION="conductor_${RELEASE_VERSION:1}"

mkdir -p build/${VERSION}/DEBIAN
mkdir -p build/${VERSION}/opt/conductor
mkdir -p build/${VERSION}/etc/profile.d

cp -r ../../bin \
      ../../conductor \
      ../../maya_shelf \
      ../../nuke_menu \
      ../../clarisse_shelf \
       build/${VERSION}/opt/conductor

mv build/${VERSION}/opt/conductor/bin/conductor build/${VERSION}/opt/conductor/bin/conductor_client
cp conductor build/${VERSION}/opt/conductor/bin/conductor
cp conductor.sh build/${VERSION}/etc/profile.d

cp control  build/${VERSION}/DEBIAN
echo "Version: ${RELEASE_VERSION:1}" >> build/${VERSION}/DEBIAN/control
sudo chown -R root:root build/${VERSION}

for dist_ver in xenial trusty precise; do
    cp -r build build-${dist_ver}
    
    docker run -i \
      -v ${WORKSPACE}/installers/Python-2.7.11:/root/src \
      -v $(pwd)/build-${dist_ver}/opt/conductor/python:/root/python \
      -v $(pwd)/build-python.sh:/root/build-python.sh \
      ubuntu:${dist_ver} \
      /root/build-python.sh
    
    sudo dpkg-deb --build build-${dist_ver}/${VERSION}
    sudo chown -R jenkins:jenkins build-${dist_ver}/${VERSION}
    mv  build-${dist_ver}/${VERSION}.deb .//${VERSION}-${dist_ver}.deb
    
    #upload our asset to GitHub
    curl -s -u \
        ${GITHUB_API_TOKEN} \
        --data-binary @build/${VERSION}-${dist_ver}.deb	 \
        -H "Content-Type:application/octet-stream" \
        "${UPLOAD_URL}?name=${VERSION}-${dist_ver}.deb"
done
popd
