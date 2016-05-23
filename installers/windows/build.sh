#!/bin/bash
pushd $( dirname "${BASH_SOURCE[0]}" )
PATH=$PATH:./nsis/bin

mkdir -p ./Conductor
cp -r ../../bin ../../conductor ../../maya_shelf ../../nuke_menu ../../clarisse_shelf ./python ./conductor.bat ./Conductor

makensis /DVERSION="${RELEASE_VERSION}" /DINSTALLER_NAME="conductor-${RELEASE_VERSION}" ConductorClient.nsi

popd
