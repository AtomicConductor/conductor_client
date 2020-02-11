#!/bin/bash

RELEASE_VERSION=${CI_BRANCH}

with_client=false
if [ $# -eq 1 ] && [ $1 = "--with_client" ] ; then
    if [  !  -f /artifacts/build/dc/current-version.txt ] ; then
        echo "Desktop client does not exist"
        exit 1
    fi
    with_client=true
fi

if [ $with_client = true ]; then
    DESKTOP_CLIENT_DIR=/artifacts/build/dc/win64
    cp -r  ${DESKTOP_CLIENT_DIR}/* ${BUILD_DIR}/Conductor
    version=$( cat /artifacts/build/dc/current-version.txt | cut -d" " -f1 )
    RELEASE_VERSION="v${version}"
fi

osslsigncode sign -pkcs12 /src/installers/certificates/authenticode-certificate.p12 -pass ${WINDOWS_INSTALLER_CERTIFICATE_PWORD} -n "Conductor Client" -i "https://www.conductortech.com/" -in /artifacts/conductor-${RELEASE_VERSION}.unsigned.exe -out /artifacts/conductor-${RELEASE_VERSION}.exe