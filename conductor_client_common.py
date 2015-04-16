import os
import logging

if os.environ.has_key('DEVELOPMENT'):
    logging.basicConfig(level='DEBUG')
    CONDUCTOR_URL = "http://localhost:8080/"
    BUCKET_NAME = 'conductor'
else:
    BUCKET_NAME = 'output_render'
    CONDUCTOR_URL = "https://3-dot-atomic-light-001.appspot.com/"
    logging.basicConfig(level='INFO')
