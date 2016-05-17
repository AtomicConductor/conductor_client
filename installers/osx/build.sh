#!/bin/bash
pushd $( dirname "${BASH_SOURCE[0]}" )

mkdir -p build/Conductor.app/Contents/MacOS build/Conductor.app/Contents/Resources build/Library/LaunchAgents
cp -r ../../bin ../../conductor ../../maya_shelf ../../nuke_menu ../../clarisse_shelf ./python build/Conductor.app/Contents/MacOS
cp info.plist build/Conductor.app/Contents
cp com.conductorio.conductor.plist build/Library/LaunchAgents

popd

