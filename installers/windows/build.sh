#!/bin/bash -x
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
      ${BUILD_DIR}/Conductor

cp -r ${SRC_DIR}/installers/windows/conductor_128.ico \
      ${SRC_DIR}/installers/windows/ConductorClient.nsi \
      ${SRC_DIR}/installers/windows/EnvVarUpdate.nsh \
      ${SRC_DIR}/installers/windows/eula.txt \
      ${SRC_DIR}/installers/windows/nsis \
      ${BUILD_DIR}

pushd ${BUILD_DIR}
./nsis/bin/makensis -DVERSION="${RELEASE_VERSION:1}.0"\
                    -DINSTALLER_NAME="/artifacts/conductor-${RELEASE_VERSION}.exe"\
                    ConductorClient.nsi

popd
