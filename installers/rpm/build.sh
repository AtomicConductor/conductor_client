#!/bin/bash -xe
pushd $( dirname "${BASH_SOURCE[0]}" )


with_client=false
if [ $# -eq 2 ] && [ $2 = "--with_client" ] ; then
    if [  !  -f /artifacts/build/dc/linux64/current-version.txt ] ; then
        echo "Desktop client does not exist"
        exit 1
    fi
    version=$( cat /artifacts/build/dc/win64/current-version.txt | cut -d" " -f1 )
    RELEASE_VERSION="v${version}"
    with_client=true
else
    RELEASE_VERSION=${CI_BRANCH}
fi




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

if [ $with_client = true ]; then
    DESKTOP_CLIENT_DIR=/artifacts/build/dc/linux64
    cp -r  ${DESKTOP_CLIENT_DIR}/* ${RPM_BUILDROOT}/opt/conductor
fi

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
