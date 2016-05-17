#!/bin/bash -x
#This is mostly based on the tutorial:
#http://bomutils.dyndns.org/tutorial.html
pushd $( dirname "${BASH_SOURCE[0]}" )

<<<<<<< HEAD
<<<<<<< HEAD
VERSION=${RELEASE_VERSION:1}
=======
VERSION=${MAJOR_VERSION}.${MINOR_VERSION}.${PATCH_VERSION}
=======
VERSION=${RELEASE_VERSION:1}
>>>>>>> d47736c... cleanup version strings

>>>>>>> cfa5cb5... release versions
#Create required directory structure
mkdir -p build/flat/base.pkg build/flat/Resources/en.lproj
mkdir -p build/root/Applications/Conductor.app/Contents/MacOS build/root/Applications/Conductor.app/Contents/Resources
mkdir -p build/root/Library/LaunchAgents
mkdir -p build/root/etc/paths.d
mkdir -p build/scripts
#Copy source files
<<<<<<< HEAD
<<<<<<< HEAD
=======
>>>>>>> 520c972... osx fix
cp -r ../../bin \
      ../../conductor \
      ../../maya_shelf \
      ../../nuke_menu \
      ../../clarisse_shelf \
      ./python \
      build/root/Applications/Conductor.app/Contents/MacOS
<<<<<<< HEAD
=======
cp -r ../../bin ../../conductor ../../maya_shelf ../../nuke_menu ../../clarisse_shelf ./python build/root/Applications/Conductor.app/Contents/MacOS
<<<<<<< HEAD
cp info.plist build/root/Applications/Conductor.app/Contents
>>>>>>> a76bc40... fix missing setenv
=======
>>>>>>> cfa5cb5... release versions
=======
>>>>>>> 520c972... osx fix
cp setenv build/root/Applications/Conductor.app/Contents/MacOS
cp Conductor.icns build/root/Applications/Conductor.app/Contents/Resources
cp com.conductorio.conductor.plist build/root/Library/LaunchAgents
<<<<<<< HEAD
<<<<<<< HEAD
cp postinstall preinstall build/scripts
mv build/root/Applications/Conductor.app/Contents/MacOS/bin/conductor \
    build/root/Applications/Conductor.app/Contents/MacOS/bin/conductor_client
cp conductor build/root/Applications/Conductor.app/Contents/MacOS/bin
echo "/Applications/Conductor.app/Contents/MacOS/bin" > build/root/etc/paths.d/conductor

sed "s/{VERSION}/${VERSION}/" info.plist > build/root/Applications/Conductor.app/Contents/info.plist
=======
cp postinstall build/scripts
mv build/root/Applications/Conductor.app/Contents/MacOS/bin/conductor \
    build/root/Applications/Conductor.app/Contents/MacOS/bin/conductor_client
cp conductor build/root/Applications/Conductor.app/Contents/MacOS/bin
>>>>>>> b95d609... OS X use packaged python
=======
cp postinstall preinstall build/scripts
mv build/root/Applications/Conductor.app/Contents/MacOS/bin/conductor \
    build/root/Applications/Conductor.app/Contents/MacOS/bin/conductor_client
cp conductor build/root/Applications/Conductor.app/Contents/MacOS/bin
echo "/Applications/Conductor.app/Contents/MacOS/bin" > build/root/etc/paths.d/conductor
>>>>>>> 4db55ed... OS X preinstall cleanup

<<<<<<< HEAD
PKG_FILES=$(find build/root | wc -l)
PKG_DU=$(du -b -s build/root | cut -f1)
sed "s/{PKG_DU}/${PKG_DU}/g;s/{PKG_FILES}/${PKG_FILES}/g;s/{VERSION}/${VERSION}/g" PackageInfo > build/flat/base.pkg/PackageInfo
sed "s/{PKG_DU}/${PKG_DU}/g;s/{VERSION}/${VERSION}/g" Distribution > build/flat/Distribution
=======
sed "s/{VERSION}/${VERSION}/" info.plist > build/root/Applications/Conductor.app/Contents/info.plist

<<<<<<< HEAD
#Build ConductorClient.pkg
>>>>>>> cfa5cb5... release versions
pushd build
PKG_FILES=$(find root | wc -l)
PKG_DU=$(du -b -s root | cut -f1)
=======
PKG_FILES=$(find build/root | wc -l)
PKG_DU=$(du -b -s build/root | cut -f1)
<<<<<<< HEAD
>>>>>>> 4693ac6... python build script
sed "s/{PKG_DU}/${PKG_DU}/g;s/{PKG_FILES}/${PKG_FILES}/g;s/{VERSION}/${VERSION}/g" PackageInfo > flat/base.pkg/PackageInfo
sed "s/{PKG_DU}/${PKG_DU}/g;s/{VERSION}/${VERSION}/g" Distribution > flat/Distribution
=======
sed "s/{PKG_DU}/${PKG_DU}/g;s/{PKG_FILES}/${PKG_FILES}/g;s/{VERSION}/${VERSION}/g" PackageInfo > build/flat/base.pkg/PackageInfo
sed "s/{PKG_DU}/${PKG_DU}/g;s/{VERSION}/${VERSION}/g" Distribution > build/flat/Distribution
>>>>>>> 520c972... osx fix
pushd build
( cd root && find . | cpio -o --format odc --owner 0:80 | gzip -c ) > flat/base.pkg/Payload
( cd scripts && find . | cpio -o --format odc --owner 0:80 | gzip -c ) > flat/base.pkg/Scripts
../utils/mkbom -u 0 -g 80 root flat/base.pkg/Bom
( cd flat && ../../utils/xar --compression none -cf "../../conductor-${RELEASE_VERSION}.pkg" * )
<<<<<<< HEAD
<<<<<<< HEAD
popd

#upload our asset to GitHub
curl -s -u \
    ${GITHUB_API_TOKEN} \
    --data-binary @conductor-${RELEASE_VERSION}.pkg \
    -H "Content-Type:application/octet-stream" \
    "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}.pkg"
=======
>>>>>>> 41d5af4... osx fix
=======
popd
<<<<<<< HEAD
popd
<<<<<<< HEAD
>>>>>>> ab0e5a1... build.sh fixes
=======
>>>>>>> 736ceed... library version string
popd
<<<<<<< HEAD
=======
popd
=======
>>>>>>> 51fc306... path fixes

#upload our asset to GitHub
curl -s -u \
    ${GITHUB_API_TOKEN} \
    --data-binary @conductor-${RELEASE_VERSION}.pkg \
    -H "Content-Type:application/octet-stream" \
    "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}.pkg"
<<<<<<< HEAD
>>>>>>> c81106b... top level build script
=======
popd
>>>>>>> 51fc306... path fixes
