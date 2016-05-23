#!/bin/bash -x
pushd $( dirname "${BASH_SOURCE[0]}" )
PATH=$PATH:./nsis/bin

mkdir -p ./Conductor
cp -r ../../bin ../../conductor ../../maya_shelf ../../nuke_menu ../../clarisse_shelf ./python ./conductor.bat ./Conductor

makensis -DVERSION="${RELEASE_VERSION:1}.0" -DINSTALLER_NAME="conductor-${RELEASE_VERSION}.exe" ConductorClient.nsi

popd
