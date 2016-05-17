#!/bin/bash -x
#This is mostly based on the tutorial:
#http://bomutils.dyndns.org/tutorial.html
pushd $( dirname "${BASH_SOURCE[0]}" )

VERSION=${RELEASE_VERSION:1}
 
#Create required directory structure
mkdir -p build/flat/base.pkg build/flat/Resources/en.lproj
mkdir -p build/root/Applications/Conductor.app/Contents/MacOS build/root/Applications/Conductor.app/Contents/Resources
mkdir -p build/root/Library/LaunchAgents
mkdir -p build/root/etc/paths.d
mkdir -p build/scripts

#Copy source files
cp -r ../../bin \
      ../../conductor \
      ../../maya_shelf \
      ../../nuke_menu \
      ../../clarisse_shelf \
      ./python \
      build/root/Applications/Conductor.app/Contents/MacOS
cp setenv build/root/Applications/Conductor.app/Contents/MacOS
cp Conductor.icns build/root/Applications/Conductor.app/Contents/Resources
cp com.conductorio.conductor.plist build/root/Library/LaunchAgents
cp postinstall preinstall build/scripts
mv build/root/Applications/Conductor.app/Contents/MacOS/bin/conductor \
    build/root/Applications/Conductor.app/Contents/MacOS/bin/conductor_client
cp conductor build/root/Applications/Conductor.app/Contents/MacOS/bin
echo "/Applications/Conductor.app/Contents/MacOS/bin" > build/root/etc/paths.d/conductor

sed "s/{VERSION}/${VERSION}/" info.plist > build/root/Applications/Conductor.app/Contents/info.plist

PKG_FILES=$(find build/root | wc -l)
PKG_DU=$(du -k -s build/root | cut -f1)
sed "s/{PKG_DU}/${PKG_DU}/g;s/{PKG_FILES}/${PKG_FILES}/g;s/{VERSION}/${VERSION}/g" PackageInfo > build/flat/base.pkg/PackageInfo
sed "s/{PKG_DU}/${PKG_DU}/g;s/{VERSION}/${VERSION}/g" Distribution > build/flat/Distribution
pushd build
( cd root && find . | cpio -o --format odc --owner 0:80 | gzip -c ) > flat/base.pkg/Payload
( cd scripts && find . | cpio -o --format odc --owner 0:80 | gzip -c ) > flat/base.pkg/Scripts
../utils/mkbom -u 0 -g 80 root flat/base.pkg/Bom
( cd flat && ../../utils/xar --compression none -cf "../../conductor-${RELEASE_VERSION}.pkg" * )
popd

#upload our asset to GitHub
curl -s -u \
    ${GITHUB_API_TOKEN} \
    --data-binary @conductor-${RELEASE_VERSION}.pkg \
    -H "Content-Type:application/octet-stream" \
    "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}.pkg"

popd

