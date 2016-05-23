#!/bin/bash -x
pushd $( dirname "${BASH_SOURCE[0]}" )

VERSION="conductor-${RELEASE_VERSION}-0.noarch"

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
rpmbuild --define "_topdir ${PWD}" \
         --define "_version ${RELEASE_VERSION}" \
         -bb SPECS/conductor.spec
mv RPMS/*/*.rpm ..
popd
popd
