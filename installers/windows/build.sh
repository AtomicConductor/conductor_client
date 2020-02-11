#!/bin/bash -x

with_client=false
if [ $# -eq 1 ] && [ $1 = "--with_client" ] ; then
    if [  !  -f /artifacts/build/dc/current-version.txt ] ; then
        echo "Desktop client does not exist"
        exit 1
    fi
    with_client=true
fi

pushd $( dirname "${BASH_SOURCE[0]}" )
RELEASE_VERSION=${CI_BRANCH}
SRC_DIR=/src
BUILD_DIR=/artifacts/build/windows

mkdir -p ${BUILD_DIR}/Conductor
cp -r ${SRC_DIR}/bin \
      ${SRC_DIR}/conductor \
      ${SRC_DIR}/maya_shelf \
      ${SRC_DIR}/nuke_menu \
      ${SRC_DIR}/installers/windows/python \
      ${SRC_DIR}/installers/windows/conductor.bat \
      ${SRC_DIR}/installers/windows/companion-icon.ico \
      ${BUILD_DIR}/Conductor

cp -r ${SRC_DIR}/installers/windows/conductor_128.ico \
      ${SRC_DIR}/installers/windows/ConductorClient.nsi \
      ${SRC_DIR}/installers/windows/EnvVarUpdate.nsh \
      ${SRC_DIR}/installers/windows/eula.txt \
      ${SRC_DIR}/installers/windows/nsis \
      ${BUILD_DIR}

if [ $with_client = true ]; then
    DESKTOP_CLIENT_DIR=/artifacts/build/dc/win64
    cp -r  ${DESKTOP_CLIENT_DIR}/* ${BUILD_DIR}/Conductor
    version=$( cat /artifacts/build/dc/current-version.txt | cut -d" " -f1 )
    RELEASE_VERSION="v${version}"
fi

pushd ${BUILD_DIR}
if [ $with_client = true ]; then
    ./nsis/bin/makensis -DVERSION="${RELEASE_VERSION:1}.0"\
                        -DWITH_CLIENT="1"\
                        -DINSTALLER_NAME="/artifacts/conductor-${RELEASE_VERSION}.unsigned.exe"\
                        ConductorClient.nsi
else
    ./nsis/bin/makensis -DVERSION="${RELEASE_VERSION:1}.0"\
                        -DINSTALLER_NAME="/artifacts/conductor-${RELEASE_VERSION}.unsigned.exe"\
                        ConductorClient.nsi
fi
popd
