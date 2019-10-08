#!/bin/sh

# Deploy files to AWS
version=$( cat /artifacts/build/dc/current-version.txt | cut -d" " -f1 )

bucket=s3://${AWS_S3_BUCKET_NAME}/conductor-desktop/
cd /artifacts
aws s3 cp ./conductor-v${version}.pkg ${bucket}
aws s3 cp ./conductor-v${version}.exe ${bucket}
aws s3 cp ./conductor-v${version}-0.el6.x86_64.rpm ${bucket}
aws s3 cp ./conductor-v${version}-0.el7.x86_64.rpm ${bucket}

aws s3 cp ./conductor-v${version}.pkg ${bucket}/conductor-latest.pkg
aws s3 cp ./conductor-v${version}.exe ${bucket}/conductor-latest.exe
aws s3 cp ./conductor-v${version}-0.el6.x86_64.rpm ${bucket}/conductor-latest-0.el6.x86_64.rpm
aws s3 cp ./conductor-v${version}-0.el7.x86_64.rpm ${bucket}/conductor-latest-0.el7.x86_64.rpm
