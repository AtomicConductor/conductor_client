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
<<<<<<< e5015bc3793aa4c3b096602b6650fd9413f593f4
    cp -r build build-${dist_ver}
    
    docker run -i \
      -v ${WORKSPACE}/installers/Python-2.7.11:/root/src \
      -v $(pwd)/build-${dist_ver}/${VERSION}/opt/conductor/python:/root/python \
=======
    cp -r build/${VERSION} build/${VERSION}-${dist-ver}
    
    docker run -i \
      -v ${WORKSPACE}/installers/Python-2.7.11:/root/src \
      -v $(pwd)/build-${dist_ver}/opt/conductor/python:/root/python \
>>>>>>> Centos 5 support; ubuntu versions
      -v $(pwd)/build-python.sh:/root/build-python.sh \
      ubuntu:${dist_ver} \
      /root/build-python.sh
    
<<<<<<< e5015bc3793aa4c3b096602b6650fd9413f593f4
    sudo dpkg-deb --build build-${dist_ver}/${VERSION}
    sudo chown -R jenkins:jenkins build-${dist_ver}/${VERSION}
    mv  build-${dist_ver}/${VERSION}.deb ./${VERSION}-${dist_ver}.deb
    
    #upload our asset to GitHub
    curl -s -u \
        ${GITHUB_API_TOKEN} \
        --data-binary @${VERSION}-${dist_ver}.deb	 \
        -H "Content-Type:application/octet-stream" \
        "${UPLOAD_URL}?name=${VERSION}-${dist_ver}.deb"
=======
    sudo dpkg-deb --build build/${VERSION}-${dist_ver}
    sudo chown -R jenkins:jenkins build/${VERSION}-${dist_ver}
    mv build/${VERSION}-${dist_ver}.deb .
>>>>>>> Centos 5 support; ubuntu versions
done
popd
