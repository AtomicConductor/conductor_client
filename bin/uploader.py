#!/usr/bin/env python

import json
import os
import sys
import imp
import time
import traceback

try:
    imp.find_module('conductor')

except:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))


import conductor, conductor.setup
from conductor.setup import *
from conductor.lib import uploader, api_client


sleep_time = 10


uploader = uploader.Uploader()
api_client = api_client.ApiClient()

logger.info('launching uploader')
while True:
    try:
        response_string, response_code = api_client.make_request(
            '/uploads/client/next',
            data='{}', # TODO: pass content type correctly in api_client
            verb='PUT')
        if response_code == 204:
            logger.debug('no files to upload')
            sys.stdout.write('.')
            sys.stdout.flush()
            time.sleep(sleep_time)
            continue
        elif response_code != 201:
            logger.error('recieved invalid response code from app %s', response_code)
            logger.error('response is %s', response_string)
            time.sleep(sleep_time)
            continue

        print '' # to make a newline after the 204 loop
        logger.debug('recieved next upload from app: %s\n\t%s', response_code, response_string)

        try:
            json_data = json.loads(response_string)
            logger.debug('json_data is: %s', json_data)
            upload_files = json_data['upload_files'].split(',')
            logger.debug('upload_files is: %s', upload_files)
        except ValueError, e:
            logger.error('response was not valid json: %s', response_string)
            time.sleep(sleep_time)
            continue

        upload_id = json_data['upload_id']


        logger.info('uploading files for upload task %s: \n\t%s', upload_id, "\n\t".join(upload_files))
        uploader.run_uploads(upload_files)
        logger.info('done uploading files')

        finish_dict = {'upload_id':upload_id, 'status':'server_pending'}
        response_string, response_code = api_client.make_request(
            '/uploads/%s/finish' % upload_id,
            data=json.dumps(finish_dict),
            verb='PUT')


    except Exception, e:
        logger.error('hit exception %s', e)
        logger.error(traceback.format_exc())
        time.sleep(sleep_time)
        continue


logger.info('exiting uploader')
