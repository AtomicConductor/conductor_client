#!/bin/bash -xe
#This is mostly based on the tutorial:
#http://bomutils.dyndns.org/tutorial.html
pushd $( dirname "${BASH_SOURCE[0]}" )

RELEASE_VERSION=${CI_BRANCH}
VERSION=${RELEASE_VERSION:1}
BUILD_DIR=/artifacts/build/osx
UTIL_DIR=$(pwd)/utils

#Create required directory structure
mkdir -p ${BUILD_DIR}/flat/base.pkg 
mkdir -p ${BUILD_DIR}/flat/Resources/en.lproj
mkdir -p ${BUILD_DIR}/root/Applications/Conductor.app/Contents/MacOS 
mkdir -p ${BUILD_DIR}/root/Applications/Conductor.app/Contents/Resources
mkdir -p ${BUILD_DIR}/root/Library/LaunchAgents
mkdir -p ${BUILD_DIR}/root/etc/paths.d
mkdir -p ${BUILD_DIR}/scripts

#Copy source files
cp -r ../../bin \
      ../../conductor \
      ../../maya_shelf \
      ../../nuke_menu \
      ./python \
      ${BUILD_DIR}/root/Applications/Conductor.app/Contents/MacOS
cp setenv ${BUILD_DIR}/root/Applications/Conductor.app/Contents/MacOS
cp Conductor.icns ${BUILD_DIR}/root/Applications/Conductor.app/Contents/Resources
cp com.conductorio.conductor.plist ${BUILD_DIR}/root/Library/LaunchAgents
cp postinstall preinstall ${BUILD_DIR}/scripts
mv ${BUILD_DIR}/root/Applications/Conductor.app/Contents/MacOS/bin/conductor \
    ${BUILD_DIR}/root/Applications/Conductor.app/Contents/MacOS/bin/conductor_client
cp conductor ${BUILD_DIR}/root/Applications/Conductor.app/Contents/MacOS/bin
echo "/Applications/Conductor.app/Contents/MacOS/bin" > ${BUILD_DIR}/root/etc/paths.d/conductor
sed "s/{VERSION}/${VERSION}/" info.plist > ${BUILD_DIR}/root/Applications/Conductor.app/Contents/info.plist

PKG_FILES=$(find ${BUILD_DIR}/root | wc -l)
PKG_DU=$(du -k -s ${BUILD_DIR}/root | cut -f1)

sed "s/{PKG_DU}/${PKG_DU}/g;s/{PKG_FILES}/${PKG_FILES}/g;s/{VERSION}/${VERSION}/g" PackageInfo > ${BUILD_DIR}/flat/base.pkg/PackageInfo
sed "s/{PKG_DU}/${PKG_DU}/g;s/{VERSION}/${VERSION}/g" Distribution > ${BUILD_DIR}/flat/Distribution
pushd ${BUILD_DIR}
( cd root && find . | cpio -o --format odc --owner 0:80 | gzip -c ) > flat/base.pkg/Payload
( cd scripts && find . | cpio -o --format odc --owner 0:80 | gzip -c ) > flat/base.pkg/Scripts
${UTIL_DIR}/mkbom -u 0 -g 80 root flat/base.pkg/Bom
( cd flat && xar --compression none -cf "/artifacts/conductor-${RELEASE_VERSION}.pkg" * )
popd
popd
