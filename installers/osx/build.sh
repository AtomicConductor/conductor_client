#!/bin/bash
pushd $( dirname "${BASH_SOURCE[0]}" )

mkdir -p build/Conductor.app/Contents/MacOS build/Conductor.app/Contents/Resources build/Library/LaunchAgents
cp -r ../../bin ../../conductor ../../maya_shelf ../../nuke_menu ../../clarisse_shelf ./python build/Conductor.app/Contents/MacOS
cp info.plist build/Conductor.app/Contents
cp Conductor.icns build/Conductor.app/Contents/Resources
cp com.conductorio.conductor.plist build/Library/LaunchAgents

dd if=/dev/zero of=ConductorClient.dmg bs=1M count=64
/sbin/mkfs.hfsplus -v ConductorClient ConductorClient.dmg
mkdir mnt
sudo mount -o loop ConductorClient.dmg mnt
cp -r build/Conductor.app mnt
sudo umount mnt

popd

