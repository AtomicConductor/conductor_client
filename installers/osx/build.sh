#!/bin/bash
pushd $( dirname "${BASH_SOURCE[0]}" )

mkdir -p build/flat/base.pkg build/flat/Resources/en.lproj
mkdir -p build/root/Applications/Conductor.app/Contents/MacOS build/root/Applications/Conductor.app/Contents/Resources
mkdir -p build/root/Library/LaunchAgents
cp -r ../../bin ../../conductor ../../maya_shelf ../../nuke_menu ../../clarisse_shelf ./python build/root/ApplicationsConductor.app/Contents/MacOS
cp info.plist build/root/Applications/Conductor.app/Contents
cp conductor_client build/root/Applications/Conductor.app/Contents/MacOS
cp Conductor.icns build/root/Applications/Conductor.app/Contents/Resources
cp com.conductorio.conductor.plist build/root/Library/LaunchAgents

pushd build
( cd root && find . | cpio -o --format odc --owner 0:80 | gzip -c ) > flat/base.pkg/Payload


dd if=/dev/zero of=ConductorClient.dmg bs=1M count=64
/sbin/mkfs.hfsplus -v ConductorClient ConductorClient.dmg
mkdir mnt
sudo mount -o loop ConductorClient.dmg mnt
sudo cp -r build/root/Applications/Conductor.app mnt
sudo umount mnt

popd

