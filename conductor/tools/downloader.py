#!/usr/bin/env python

""" Command Line Process to run downloads.
"""

import os
import sys
import time
import argparse
import httplib2
import urllib2
import json
import random
import traceback
import logging

from apiclient import discovery
from apiclient.errors import HttpError
from oauth2client import file as oauthfile
from oauth2client import client
from oauth2client import tools

import submit_settings
import conductor_client_common

# TODO
from lib.common import logging, retry, Config

class Download(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser(description=self.__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter, parents=[tools.argparser])
        self.userpass = self.get_token()
        self.service = self._auth_service()


    def _auth_service(self):
        credentials = self._get_credentials()
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = discovery.build('storage', submit_settings._API_VERSION, http=http)
        return service

    def _get_credentials(self):
        flags = self.parser.parse_args()
        storage = oauthfile.Storage(os.path.join(os.path.dirname(__file__), 'auth','conductor.dat'))
        credentials = storage.get()
        if credentials is None or credentials.invalid:
            credentials = tools.run_flow(submit_settings.FLOW, storage, flags)
        return credentials

    def get_token(self):
        token_path = os.path.join(os.path.dirname(__file__), 'auth/CONDUCTOR_TOKEN.pem')
        if not os.path.exists(token_path):
            raise IOError("Could not locate .pem file: %s" % token_path)
        with open(token_path, 'r') as f:
            user = f.read()
        userpass = "%s:unused" % user.rstrip()
        return userpass


    def make_request(self,url,json_data=None):
        logging.debug("connecting to conductor at: " + url)
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, url, self.userpass.split(':')[0], 'unused')
        auth = urllib2.HTTPBasicAuthHandler(password_manager)
        opener = urllib2.build_opener(auth)
        urllib2.install_opener(opener)
        req = urllib2.Request(
            url,
            headers = {'Content-Type':'application/json',
                       'Accepts':'application/json'},
            data=json_data)
        handler = urllib2.urlopen(req)
        logging.debug("response code was %s" % handler.getcode())
        return handler

    def get_download(self):
        ''' get a new file to download from the server or 404 '''
        download_url = CONDUCTOR_URL + 'downloads/next'
        response = self.make_request(download_url)
        if response.getcode() == '201':
            logging.info("new file to download:\n" + response.read())

        return response

    def set_download_status(self,download_id,status):
        ''' update status of download '''
        status_url = CONDUCTOR_URL + 'downloads/status'
        post_dic = {
            'download_id': download_id,
            'status': status
        }
        response = self.make_request(status_url,json.dumps(post_dic))
        logging.info("updated status:\n" + response.read())
        return response

    def main(self):
        while True:
            download_id = None
            try:
                response = self.get_download()
            except Exception, e:
                logging.error("Failed to get download! %s" % e)
                logging.error(traceback.format_exc())
                time.sleep(30)
                continue
            try:
                logging.debug("beginging download loop")
                if response.getcode() == 201:
                    try:
                        resp_data = json.loads(response.read())
                        logging.debug("response data is:\n" + str(resp_data))
                    except Exception, e:
                        logging.error("Response from server was not json! %s" % e)
                        logging.error(traceback.format_exc())
                        time.sleep(15)
                        continue
                    resp_source = resp_data['source']
                    download_id = resp_data['download_id']
                    logging.debug("resp_source is " +  resp_source)
                    resp_source_path = "%s/" % '/'.join(resp_source.split('/')[3:-1])
                    logging.debug("resp_source_path is: " + resp_source_path)
                    fields_to_return = "items(name)"

                    logging.debug("excuting request")
                    resp = req.execute()
                    logging.debug( "completed request. resp is %s" % resp)
                    logging.debug("resp_source is " + resp_source)
                    frame = resp_source.split('*')[1]
                    logging.debug("got frame: " + frame)
                    sources = []
                    logging.debug( "entering resp loop")
                    for i in resp['items']:
                        logging.debug("in item loop. looking for frame: " + frame)
                        if frame in i['name']:
                            logging.debug("found frame %s in %s" % (frame, i['name']))
                            sources.append(i['name'])

                            download_url = i['download_url']
                            source = i['name']
                            file_name = source.split('/')[-1]
                            imageSrcPath = source.split(resp_source_path)[-1]
                            if "/" in imageSrcPath:
                                subDir = "/".join(imageSrcPath.split('/')[:-1])
                            else:
                                subDir = ""
                            resp_dest = resp_data['destination']
                            destination_dir = os.path.join(resp_dest, subDir)
                            destination = os.path.join(destination_dir, file_name)
                            logging.debug( "destination is: " + destination)

                            if not os.path.exists(os.path.dirname(destination)):
                                os.makedirs(os.path.dirname(destination), 0775)
                            logging.debug("Source: %s" % source)
                            logging.debug("SubDir: %s" % subDir)
                            logging.debug("Destination: %s" % destination)


                            CHUNKSIZE = 8192

                            def chunk_report(bytes_so_far, chunk_size, total_size):
                                percent = float(bytes_so_far) / total_size
                                percent = round(percent*100, 2)


                                logging.info("Downloaded %d of %d bytes (%0.2f%%)\r" %
                                    (bytes_so_far, total_size, percent))

                                if bytes_so_far >= total_size:
                                    logging.info('\n')

                            def chunk_read(response, chunk_size=CHUNKSIZE, report_hook=None):
                                total_size = response.info().getheader('Content-Length').strip()
                                total_size = int(total_size)
                                bytes_so_far = 0


                                self.set_download_status(download_id,'downloading')
                                download_file = open(destination, 'w')
                                tick = time.time()
                                while 1:
                                    if (time.time() - tick) > 60:
                                        self.set_download_status(download_id,'downloading')
                                        tick = time.time()

                                        chunk = response.read(chunk_size)
                                        bytes_so_far += len(chunk)
                                        download_file.write(chunk)

                                    if not chunk:
                                        break

                                    if report_hook:
                                        report_hook(bytes_so_far, chunk_size, total_size)

                                return bytes_so_far


                            response = urllib2.urlopen(download_url)
                            chunk_read(response, report_hook=chunk_report

                            download_file.close()
                            logging.info( 'Download Complete!')
                            if "/publish/" in destination:
                                os.chmod(destination, 0755)
                            else:
                                os.chmod(destination, 0775)
                        else:
                            logging.debug( "there is no frame in %s" % i['name'])
                    logging.debug( "done with resp loop")
                    self.set_download_status(download_id,'downloaded')
                else:
                    logging.debug("nothing to download. sleeping...")
                    time.sleep(5)
            except Exception, e:
                logging.error( "caught exception %s" % e)
                logging.error(traceback.format_exc())
                # add error checking
                if not download_id == None:
                    self.set_download_status(download_id,'pending')
                # Please include this sleep, to ensure that the Conductor
                # does not get flooded with unnecessary requests.
                time.sleep(4)



if __name__ == "__main__":
    downloader = Download()
    downloader.main()
