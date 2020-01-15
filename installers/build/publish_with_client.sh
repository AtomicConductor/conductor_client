#!/bin/sh

# Deploy files to AWS
version=$( cat /artifacts/build/dc/current-version.txt | cut -d" " -f1 )
headers="--metadata-directive REPLACE --cache-control max-age=0,no-cache,no-store,must-revalidate --acl public-read"

bucket=s3://${AWS_S3_BUCKET_NAME}/companion/
cd /artifacts


aws s3 cp ./conductor-v${version}.pkg ${bucket} ${headers}
aws s3 cp ./conductor-v${version}.exe ${bucket} ${headers}
aws s3 cp ./conductor-v${version}-0.el6.x86_64.rpm ${bucket} ${headers}
aws s3 cp ./conductor-v${version}-0.el7.x86_64.rpm ${bucket} ${headers}

# Generate copies with static name: latest
aws s3 cp ${bucket}conductor-v${version}.pkg ${bucket}conductor-latest.pkg ${headers}
aws s3 cp ${bucket}conductor-v${version}.exe ${bucket}conductor-latest.exe ${headers}
aws s3 cp ${bucket}conductor-v${version}-0.el6.x86_64.rpm ${bucket}conductor-latest-0.el6.x86_64.rpm ${headers}
aws s3 cp ${bucket}conductor-v${version}-0.el7.x86_64.rpm ${bucket}conductor-latest-0.el7.x86_64.rpm ${headers}
