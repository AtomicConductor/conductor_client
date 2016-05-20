#!/bin/bash
#This is mostly based on the tutorial:
#http://bomutils.dyndns.org/tutorial.html
pushd $( dirname "${BASH_SOURCE[0]}" )

#Create required directory structure
mkdir -p build/flat/base.pkg build/flat/Resources/en.lproj
mkdir -p build/root/Applications/Conductor.app/Contents/MacOS build/root/Applications/Conductor.app/Contents/Resources
mkdir -p build/root/Library/LaunchAgents
mkdir -p build/scripts

#Copy source files
cp -r ../../bin ../../conductor ../../maya_shelf ../../nuke_menu ../../clarisse_shelf ./python build/root/Applications/Conductor.app/Contents/MacOS
cp info.plist build/root/Applications/Conductor.app/Contents
cp setenv build/root/Applications/Conductor.app/Contents/MacOS
cp Conductor.icns build/root/Applications/Conductor.app/Contents/Resources
cp com.conductorio.conductor.plist build/root/Library/LaunchAgents
cp postinstall build/scripts
mv build/root/Applications/Conductor.app/Contents/MacOS/bin/conductor build/root/Applications/Conductor.app/Contents/MacOS/bin/conductor_client
cp conductor build/root/Applications/Conductor.app/Contents/MacOS/bin

#Build ConductorClient.pkg
pushd build
PKG_FILES=$(find root | wc -l)
PKG_DU=$(du -b -s root | cut -f1)
cat << EOF > flat/base.pkg/PackageInfo
<pkg-info format-version="2" identifier="com.conductorio.Conductor.base.pkg" version="1.0.0" install-location="/" auth="root">
  <payload installKBytes="$PKG_DU" numberOfFiles="$PKG_FILES"/>
  <scripts>
    <postinstall file="./postinstall"/>
  </scripts>
<bundle-version>
    <bundle id="com.conductorio.conductor" CFBundleIdentifier="com.conductorio.conductor" path="./Applications/Conductor.app" CFBundleVersion="1"/>
</bundle-version>
</pkg-info>
EOF

cat << EOF > flat/Distribution
<?xml version="1.0" encoding="utf-8"?>
<installer-script minSpecVersion="1.000000" authoringTool="com.apple.PackageMaker" authoringToolVersion="3.0.3" authoringToolBuild="174">
    <title>Conductor</title>
    <options customize="never" allow-external-scripts="no"/>
    <domains enable_anywhere="true"/>
    <installation-check script="pm_install_check();"/>
    <script>function pm_install_check() {
  if(!(system.compareVersions(system.version.ProductVersion,'10.5') >= 0)) {
    my.result.title = 'Failure';
    my.result.message = 'You need at least Mac OS X 10.5 to install SimCow.';
    my.result.type = 'Fatal';
    return false;
  }
  return true;
}
</script>
    <choices-outline>
        <line choice="choice1"/>
    </choices-outline>
    <choice id="choice1" title="base">
        <pkg-ref id="com.conductorio.Conductor.base.pkg"/>
    </choice>
    <pkg-ref id="com.conductorio.Conductor.base.pkg" installKBytes="$PKG_DU" version="1.0.0" auth="Root">#base.pkg</pkg-ref>
</installer-script>
EOF

( cd root && find . | cpio -o --format odc --owner 0:80 | gzip -c ) > flat/base.pkg/Payload
( cd scripts && find . | cpio -o --format odc --owner 0:80 | gzip -c ) > flat/base.pkg/Scripts
../utils/mkbom -u 0 -g 80 root flat/base.pkg/Bom
( cd flat && ../../utils/xar --compression none -cf "../../ConductorClient.pkg" * )
popd
popd