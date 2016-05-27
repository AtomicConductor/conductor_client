#!/bin/bash -x
pushd $( dirname "${BASH_SOURCE[0]}" )

VERSION="conductor-${RELEASE_VERSION}-0.x86_64"

mkdir -p build/{BUILDROOT,RPMS,SPECS}
mkdir -p build/BUILDROOT/${VERSION}/opt/conductor
mkdir -p build/BUILDROOT/${VERSION}/etc/profile.d

cp -r ../../bin \
      ../../conductor \
      ../../maya_shelf \
      ../../nuke_menu \
      ../../clarisse_shelf \
       build/BUILDROOT/${VERSION}/opt/conductor

cp conductor.spec build/SPECS
mv build/BUILDROOT/${VERSION}/opt/conductor/bin/conductor \
    build/BUILDROOT/${VERSION}/opt/conductor/bin/conductor_client
cp conductor build/BUILDROOT/${VERSION}/opt/conductor/bin/
cp conductor.sh build/BUILDROOT/${VERSION}/etc/profile.d

for dist_ver in 6 7; do
    cp -r build build-${dist_ver}
    docker run -it \
      -v ${WORSPACE}/installers/Python-2.7.11:/root/src \
      -v $(pwd)/build/opt/conductor/python:/root/python \
      -v $(pwd)/build-python.sh:/root/build-python.sh
      centos:${dist_version} \
      /root/build-python.sh
done

pushd build
rpmbuild --define "_topdir ${PWD}" \
         --define "_version ${RELEASE_VERSION}" \
         -bb SPECS/conductor.spec
mv RPMS/*/*.rpm ..
popd
popd
