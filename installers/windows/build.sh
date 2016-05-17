#!/bin/bash -x
pushd $( dirname "${BASH_SOURCE[0]}" )
PATH=$PATH:./nsis/bin

mkdir -p ./Conductor
cp -r ../../bin ../../conductor ../../maya_shelf ../../nuke_menu ../../clarisse_shelf ./python ./conductor.bat ./Conductor

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
makensis -DVERSION="${RELEASE_VERSION:1}.0" -DINSTALLER_NAME="conductor-${RELEASE_VERSION}.exe" ConductorClient.nsi
=======
makensis /DVERSION="${RELEASE_VERSION}" /DINSTALLER_NAME="conductor-${RELEASE_VERSION}" ConductorClient.nsi
>>>>>>> cfa5cb5... release versions
=======
makensis -DVERSION="${RELEASE_VERSION}" -DINSTALLER_NAME="conductor-${RELEASE_VERSION}" ConductorClient.nsi
>>>>>>> 839cfb4... windows version fix
=======
makensis -DVERSION="${RELEASE_VERSION:1}.0" -DINSTALLER_NAME="conductor-${RELEASE_VERSION}.exe" ConductorClient.nsi
>>>>>>> 61de885... windows version fix

#upload our asset to GitHub
curl -s -u \
    ${GITHUB_API_TOKEN} \
    --data-binary @conductor-${RELEASE_VERSION}.exe \
    -H "Content-Type:application/octet-stream" \
    "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}.exe"

<<<<<<< HEAD
popd
=======
#upload our asset to GitHub
curl -s -u \
    ${GITHUB_API_TOKEN} \
    --data-binary @conductor-${RELEASE_VERSION}.exe \
    -H "Content-Type:application/octet-stream" \
    "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}.exe"

popd
>>>>>>> c81106b... top level build script
