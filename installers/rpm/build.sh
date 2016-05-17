#!/bin/bash -x
pushd $( dirname "${BASH_SOURCE[0]}" )

<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
<<<<<<< HEAD
VERSION="conductor-${RELEASE_VERSION}-0.x86_64"

mkdir -p build/{BUILDROOT,RPMS,SPECS}
mkdir -p build/BUILDROOT/${VERSION}/opt/conductor
mkdir -p build/BUILDROOT/${VERSION}/etc/profile.d
=======
MAJOR_VERSION="1"
MINOR_VERSION="0"
PATCH_VERSION="0"
VERSION="conductor-${MAJOR_VERSION}-${MINOR_VERSION}.x86_64"
=======
VERSION="conductor-${MAJOR_VERSION}-${MINOR_VERSION}-${PATCH_VERSION}.x86_64"
>>>>>>> 5ca5f82... version info
=======
VERSION="conductor-${RELEASE_VERSION}-0.noarch"
>>>>>>> cfa5cb5... release versions
=======
VERSION="conductor-${RELEASE_VERSION}-0.x86_64"
>>>>>>> d47736c... cleanup version strings

mkdir -p build/{BUILDROOT,RPMS,SPECS}
<<<<<<< HEAD
mkdir -p build/BUILDROOT/opt/conductor
mkdir -p build/BUILDROOT/etc/profile.d
>>>>>>> af70b55... RPM package
=======
mkdir -p build/BUILDROOT/${VERSION}/opt/conductor
mkdir -p build/BUILDROOT/${VERSION}/etc/profile.d
>>>>>>> 75a5a80... RPM package

cp -r ../../bin \
      ../../conductor \
      ../../maya_shelf \
      ../../nuke_menu \
      ../../clarisse_shelf \
<<<<<<< HEAD
<<<<<<< HEAD
       build/BUILDROOT/${VERSION}/opt/conductor

cp conductor.spec build/SPECS
mv build/BUILDROOT/${VERSION}/opt/conductor/bin/conductor \
    build/BUILDROOT/${VERSION}/opt/conductor/bin/conductor_client
cp conductor build/BUILDROOT/${VERSION}/opt/conductor/bin/
cp conductor.sh build/BUILDROOT/${VERSION}/etc/profile.d

for dist_ver in 5 6 7; do
    cp -r build build-${dist_ver}
    docker run -i \
      -v ${WORKSPACE}/installers/Python-2.7.11:/root/src \
      -v $(pwd)/build-${dist_ver}/BUILDROOT/${VERSION}/opt/conductor/python:/root/python \
      -v $(pwd)/build-python.sh:/root/build-python.sh \
      centos:${dist_ver} \
      /root/build-python.sh
    
    mv build-${dist_ver}/BUILDROOT/${VERSION} build-${dist_ver}/BUILDROOT/conductor-${RELEASE_VERSION}-0.el${dist_ver}.x86_64
    pushd build-${dist_ver}
    rpmbuild --define "_topdir ${PWD}" \
         --define "_version ${RELEASE_VERSION}" \
         --define "_dist el${dist_ver}" \
         -bb SPECS/conductor.spec
    
    #upload our asset to GitHub
    curl -s -u \
        ${GITHUB_API_TOKEN} \
        --data-binary @RPMS/x86_64/conductor-${RELEASE_VERSION}-0.el${dist_ver}.x86_64.rpm	 \
        -H "Content-Type:application/octet-stream" \
        "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}-0.el${dist_ver}.x86_64.rpm"
    popd
done
=======
      ./python \
=======
>>>>>>> 4fcd197... dynamic python build
       build/BUILDROOT/${VERSION}/opt/conductor

cp conductor.spec build/SPECS
mv build/BUILDROOT/${VERSION}/opt/conductor/bin/conductor \
    build/BUILDROOT/${VERSION}/opt/conductor/bin/conductor_client
cp conductor build/BUILDROOT/${VERSION}/opt/conductor/bin/
cp conductor.sh build/BUILDROOT/${VERSION}/etc/profile.d

for dist_ver in 5 6 7; do
    cp -r build build-${dist_ver}
    docker run -i \
      -v ${WORKSPACE}/installers/Python-2.7.11:/root/src \
      -v $(pwd)/build-${dist_ver}/BUILDROOT/${VERSION}/opt/conductor/python:/root/python \
      -v $(pwd)/build-python.sh:/root/build-python.sh \
      centos:${dist_ver} \
      /root/build-python.sh
    
    mv build-${dist_ver}/BUILDROOT/${VERSION} build-${dist_ver}/BUILDROOT/conductor-${RELEASE_VERSION}-0.el${dist_ver}.x86_64
    pushd build-${dist_ver}
    rpmbuild --define "_topdir ${PWD}" \
         --define "_version ${RELEASE_VERSION}" \
         --define "_dist el${dist_ver}" \
         -bb SPECS/conductor.spec
<<<<<<< HEAD
<<<<<<< HEAD
mv RPMS/*/*.rpm ..
popd
popd
>>>>>>> af70b55... RPM package
=======
=======
    
    #upload our asset to GitHub
    curl -s -u \
        ${GITHUB_API_TOKEN} \
        --data-binary @RPMS/x86_64/conductor-${RELEASE_VERSION}-0.el${dist_ver}.x86_64.rpm	 \
        -H "Content-Type:application/octet-stream" \
<<<<<<< HEAD
<<<<<<< HEAD
        "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}.exe"
>>>>>>> 4af15ea... upload assets
=======
        "${UPLOAD_URL}?conductor-${RELEASE_VERSION}-0.el${dist_ver}.x86_64.rpm"
>>>>>>> 2083fa5... Centos 5 support; ubuntu versions
=======
        "${UPLOAD_URL}?name=conductor-${RELEASE_VERSION}-0.el${dist_ver}.x86_64.rpm"
>>>>>>> dfdba4d... fix ubuntu publish
    popd
done
>>>>>>> 70b650d... fix docker paths
