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
import time
import imp

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import conductor
import conductor.setup
import conductor.lib.common

# Global logger and config objects
logger = conductor.setup.logger
CONFIG = conductor.setup.CONFIG

class Download(object):
    def __init__(self):
        self.parser = argparse.ArgumentParser(description=self.__doc__,
                formatter_class=argparse.RawDescriptionHelpFormatter)
        self.userpass = self.get_token()


    def get_token(self):
        userpass = "%s:unused" % CONFIG['conductor_token']
        return userpass


    def make_request(self,url,json_data=None):
        logger.debug("connecting to conductor at: " + url)
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
        logger.debug("response code was %s" % handler.getcode())
        return handler

    def get_download(self):
        ''' get a new file to download from the server or 404 '''
        download_url = CONFIG['url'] + '/downloads/next'
        response = self.make_request(download_url)
        if response.getcode() == '201':
            logger.info("new file to download:\n" + response.read())

        return response

    def set_download_status(self,download_id,status):
        ''' update status of download '''
        status_url = CONFIG['url'] + '/downloads/status'
        post_dic = {
            'download_id': download_id,
            'status': status
        }
        response = self.make_request(status_url,json.dumps(post_dic))
        logger.info("updated status:\n" + response.read())
        return response

    def main(self):
        while True:
            download_id = None
            try:
                response = self.get_download()
            except Exception, e:
                logger.error("Failed to get download! %s" % e)
                logger.error(traceback.format_exc())
                time.sleep(30)
                continue
            try:
                logger.debug("beginging download loop")
                if response.getcode() == 201:
                    try:
                        resp_data = json.loads(response.read())
                        logger.debug("response data is:\n" + str(resp_data))
                    except Exception, e:
                        logger.error("Response from server was not json! %s" % e)
                        logger.error(traceback.format_exc())
                        time.sleep(15)
                        continue
                    download_id = resp_data['download_id']
                    for download_url,local_path in resp_data['download_urls'].iteritems():
                        logger.debug("downloading: %s to %s", download_url, local_path)
                        if not os.path.exists(os.path.dirname(local_path)):
                            os.makedirs(os.path.dirname(local_path), 0775)
                        CHUNKSIZE = 8192

                        def chunk_report(bytes_so_far, chunk_size, total_size):
                            percent = float(bytes_so_far) / total_size
                            percent = round(percent*100, 2)


                            logger.info("Downloaded %d of %d bytes (%0.2f%%)\r" %
                                (bytes_so_far, total_size, percent))

                            if bytes_so_far >= total_size:
                                logger.info('\n')

                        def chunk_read(response, chunk_size=CHUNKSIZE, report_hook=None):
                            logger.debug('chunk_size is %s', chunk_size)
                            total_size = response.info().getheader('Content-Length').strip()
                            total_size = int(total_size)
                            bytes_so_far = 0


                            self.set_download_status(download_id,'downloading')
                            download_file = open(local_path, 'w')
                            tick = time.time()
                            while 1:
                                if (time.time() - tick) > 60:
                                    self.set_download_status(download_id,'downloading')
                                    tick = time.time()

                                chunk = response.read(chunk_size)
                                bytes_so_far += len(chunk)
                                download_file.write(chunk)

                                if not chunk:
                                    download_file.close()
                                    break

                                if report_hook:
                                    report_hook(bytes_so_far, chunk_size, total_size)

                            return bytes_so_far


                        response = urllib2.urlopen(download_url)
                        chunk_read(response, report_hook=chunk_report)

                        logger.info( 'downloaded %s', local_path)
                    logger.debug( "done downloading files")
                    self.set_download_status(download_id,'downloaded')
                else:
                    logger.debug("nothing to download. sleeping...")
                    time.sleep(10)
            except Exception, e:
                logger.error( "caught exception %s" % e)
                logger.error(traceback.format_exc())
                # add error checking
                if not download_id == None:
                    self.set_download_status(download_id,'pending')
                # Please include this sleep, to ensure that the Conductor
                # does not get flooded with unnecessary requests.
                time.sleep(10)



if __name__ == "__main__":
    downloader = Download()
    downloader.main()
