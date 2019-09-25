#!/bin/bash -xe

dest=/artifacts/build/dc/macos64
if [  !  -d ${dest} ] ; then
    rm -rf ${dest}
fi

mkdir -p ${dest}
aws s3 cp s3://${AWS_S3_BUCKET_NAME}/conductor-desktop/conductor-desktop-latest-macos64.zip ${dest}
unzip ${dest}/conductor-desktop-latest-macos64.zip  -d ${dest}
