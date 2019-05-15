#!/bin/bash -xe
pushd $( dirname "${BASH_SOURCE[0]}" )

RELEASE_VERSION=${CI_BRANCH}
VERSION="conductor-${RELEASE_VERSION}-0.x86_64"
DIST_VER=${1}
BUILD_DIR=/artifacts/build/el${DIST_VER}
SRC_DIR=/src
RPM_BUILDROOT=${BUILD_DIR}/rpm/BUILDROOT/conductor-${RELEASE_VERSION}-0.el${DIST_VER}.x86_64


mkdir -p ${BUILD_DIR}
mkdir -p ${BUILD_DIR}/python
mkdir -p ${BUILD_DIR}/rpm/{BUILDROOT,RPMS,SPECS}
mkdir -p ${RPM_BUILDROOT}/opt/conductor
mkdir -p ${RPM_BUILDROOT}/etc/profile.d

pushd ${BUILD_DIR}/python
curl -s -o python.tgz "https://www.python.org/ftp/python/2.7.11/Python-2.7.11.tgz"
tar zxf python.tgz
Python*/configure --prefix=${RPM_BUILDROOT}/opt/conductor/python && \
    make && make install
curl -O "https://bootstrap.pypa.io/get-pip.py"
${RPM_BUILDROOT}/opt/conductor/python/bin/python get-pip.py
${RPM_BUILDROOT}/opt/conductor/python/bin/pip install -r ${SRC_DIR}/requirements.txt
popd

cp -r ${SRC_DIR}/bin \
      ${SRC_DIR}/conductor \
      ${SRC_DIR}/maya_shelf \
      ${SRC_DIR}/nuke_menu \
      ${RPM_BUILDROOT}/opt/conductor

cp conductor.spec ${BUILD_DIR}/rpm/SPECS
mv ${RPM_BUILDROOT}/opt/conductor/bin/conductor \
    ${RPM_BUILDROOT}/opt/conductor/bin/conductor_client
cp conductor ${RPM_BUILDROOT}/opt/conductor/bin/
cp conductor.sh ${RPM_BUILDROOT}/etc/profile.d

pushd ${BUILD_DIR}/rpm
rpmbuild --define "_topdir $(pwd)" \
         --define "_version ${RELEASE_VERSION}" \
         --define "_dist el${DIST_VER}" \
         -bb SPECS/conductor.spec
mv RPMS/x86_64/conductor-${RELEASE_VERSION}-0.el${DIST_VER}.x86_64.rpm /artifacts
popd
popd
