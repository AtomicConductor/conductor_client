#!/bin/bash -xe

# Make a directory to receive desktop client stuff and put the version file there.
dest=/artifacts/build/dc/
if [  -d ${dest} ] ; then
    rm -rf ${dest}
fi
mkdir -p ${dest}

aws s3 cp s3://${AWS_S3_BUCKET_NAME}/conductor-desktop/current-version.txt ${dest}
