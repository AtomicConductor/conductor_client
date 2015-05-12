#!/usr/bin/env python
import os
import httplib2
from oauth2client import client
from oauth2client import tools


_API_VERSION = 'v1'

# --- Auth Settings ---
CLIENT_SECRETS = os.path.join(os.path.dirname(__file__), 'auth', 'client_secrets.json')
FLOW = client.flow_from_clientsecrets(CLIENT_SECRETS,
  scope=[
      'https://www.googleapis.com/auth/devstorage.full_control',
      'https://www.googleapis.com/auth/devstorage.read_only',
      'https://www.googleapis.com/auth/devstorage.read_write',
    ],
    message=tools.message_if_missing(CLIENT_SECRETS))

_CLOUD_PROJECT = "atomic-light-001"

_SERVICE_ACCOUNT_EMAIL = "367447922845-mkbemnu75n1ahhkj2plk9gt1n0jd83ok@developer.gserviceaccount.com"

# --- Cloud Storage Copy Settings ---
DRIVE_MAPS = ["C:", "Z:"]
CHUNKSIZE = 2 * 1024 * 1024
DEFAULT_MIMETYPE = 'application/octet-stream'
NUM_RETRIES = 5
RETRYABLE_ERRORS = (httplib2.HttpLib2Error, IOError)

# Do not edit below
_BUCKET_NAME = 'conductor'
_UPLOAD_POINT = "br_upload"
_UPLOAD_FILE_POINT = "br_upload_files"
_CLOUD_ROOT = "gs://conductor/%s" % _UPLOAD_POINT # no trailing '/'
# Your Linux mount is: /Volumes/br/
# The environment variable "${CONDUCTOR_MOUNT}" points to this location