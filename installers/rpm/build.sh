#!/bin/bash -x
pushd $( dirname "${BASH_SOURCE[0]}" )

MAJOR_VERSION="1"
MINOR_VERSION="0"
PATCH_VERSION="0"

mkdir -p build/{BUILDROOT,RPMS,SPECS}
mkdir -p build/BUILDROOT/opt/conductor
mkdir -p build/BUILDROOT/etc/profile.d

cp -r ../../bin \
      ../../conductor \
      ../../maya_shelf \
      ../../nuke_menu \
      ../../clarisse_shelf \
      ./python \
       build/BUILDROOT/opt/conductor

cp conductor.spec build/SPECS
mv build/BUILDROOT/opt/conductor/bin/conductor build/BUILDROOT/opt/conductor/bin/conductor_client
cp conductor build/BUILDROOT/opt/conductor/bin/

pushd build
rpmbuild --define "_topdir ${PWD}" -bb SPECS/conductor.spec
mv RPMS/*.rpm ..
popd
popd
