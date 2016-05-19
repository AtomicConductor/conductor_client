#!/bin/bash -x
pushd $( dirname "${BASH_SOURCE[0]}" )

MAJOR_VERSION="1"
MINOR_VERSION="0"
PATCH_VERSION="0"
VERSION="conductor-${MAJOR_VERSION}-${MINOR_VERSION}.x86_64"

mkdir -p build/{BUILDROOT,RPMS,SPECS}
mkdir -p build/BUILDROOT/${VERSION}/opt/conductor
mkdir -p build/BUILDROOT/${VERSION}/etc/profile.d

cp -r ../../bin \
      ../../conductor \
      ../../maya_shelf \
      ../../nuke_menu \
      ../../clarisse_shelf \
      ./python \
       build/BUILDROOT/${VERSION}/opt/conductor

cp conductor.spec build/SPECS
mv build/BUILDROOT/${VERSION}/opt/conductor/bin/conductor build/BUILDROOT/${VERSION}/opt/conductor/bin/conductor_client
cp conductor build/BUILDROOT/${VERSION}/opt/conductor/bin/
cp conductor.sh build/BUILDROOT/${VERSION}/etc/profile.d

pushd build
rpmbuild --define "_topdir ${PWD}" -bb SPECS/conductor.spec
mv RPMS/*/*.rpm ..
popd
popd
