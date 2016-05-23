#!/bin/bash -x
pushd $( dirname "${BASH_SOURCE[0]}" )

VERSION="conductor_${MAJOR_VERSION}.${MINOR_VERSION}.${PATCH_VERSION}"

mkdir -p build/${VERSION}/DEBIAN
mkdir -p build/${VERSION}/opt/conductor
mkdir -p build/${VERSION}/etc/profile.d

cp -r ../../bin \
      ../../conductor \
      ../../maya_shelf \
      ../../nuke_menu \
      ../../clarisse_shelf \
      ./python \
       build/${VERSION}/opt/conductor

mv build/${VERSION}/opt/conductor/bin/conductor build/${VERSION}/opt/conductor/bin/conductor_client
cp conductor build/${VERSION}/opt/conductor/bin/conductor
cp conductor.sh build/${VERSION}/etc/profile.d

cp control  build/${VERSION}/DEBIAN
echo "Version: ${MAJOR_VERSION}.${MINOR_VERSION}.${PATCH_VERSION}" >> build/${VERSION}/DEBIAN/control
sudo chown -R root:root build/${VERSION}
sudo dpkg-deb --build build/${VERSION}
sudo chown -R jenkins:jenkins build/${VERSION}
mv build/${VERSION}.deb .
popd
