from boto.s3.connection import S3Connection

#  Apply any data munging to the input path for things like pulling from AWS
#  Should return an input type which is one of "file", "gcs", or "aws"
def upload_callback(input_path):

    # input_type = "file"
    path = input_path
    #
    # Example for pulling from S3.
    access_key = "AKIAJELTPEDR2S376P2Q"
    secret_key = "V2uuebSMm7/ru2xVuXKRHLBeIZkJGKgHoI9v1gml"
    input_type = 'aws'
    c = S3Connection(access_key, secret_key)
    path = c.generate_url(
        expires_in=long(1000000),
        method='GET',
        bucket="conductorio",
        key=path.split('/')[-1],
        query_auth=True,
        force_http=False
    )

    print "returning s3 path %s" % path

    return input_type, path
