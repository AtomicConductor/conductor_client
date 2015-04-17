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
import logging
import logging.handlers
import hashlib
import base64
import multiprocessing
import threading
import socket
from apiclient import discovery
from apiclient.http import MediaIoBaseDownload
from apiclient.errors import HttpError
from oauth2client import file as oauthfile
from oauth2client import tools
import submit_settings
import conductor_client_common
from conductor_client_common import BUCKET_NAME, CONDUCTOR_URL


LOGGER = conductor_client_common.setup_logger(
    __file__,
    log_dir=conductor_client_common.get_temp_dir())


class ConductorDownload(object):

    """ Command line downloader for pulling Conductor results
        Pass in a list of job ids"""
    # pylint: disable=too-many-instance-attributes
    def __init__(self, bucket_name=BUCKET_NAME, logger=LOGGER):
        """ Class attributes """
        self.start = time.time()
        self.this_file = __file__
        self.download_processes = 12
        self.layer = None
        self.out_dir = None
        self.file_prefix = None
        self.setup_args()
        self.parse_args()
        self.bucket_name = bucket_name
        self.logger = logger
        self.userpass = self._get_token()
        self.service = self._auth_service()
        self.download_pool = multiprocessing.Pool(self.download_processes)

    def setup_args(self):
        """ Add commandline arguments here """
        self.parser = argparse.ArgumentParser(
            description=self.__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
            parents=[tools.argparser])
        self.parser.add_argument(
            '-jid',
            nargs="*",
            help="job ids")
        self.parser.add_argument(
            '-out',
            type=str,
            help="override output dir to override")
        self.parser.add_argument(
            '-layer',
            type=str,
            help="override the layer name to grab")
        self.parser.add_argument(
            '-resync',
            action='store_true',
            help="Redownload any broken/additional frames")
        self.parser.add_argument(
            '-check',
            action='store_true',
            help="check valid")
        self.parser.add_argument(
            '-single_thread',
            action='store_true',
            help="single thread",
            default=False)
        self.parser.add_argument(
            '-download_threads',
            type=int,
            help="Number of download threads to run")

    def parse_args(self):
        """ parse the command line arguments and create class variables"""
        self.args = self.parser.parse_args()
        self.job_ids = self.args.jid
        self.out_dir = self.args.out
        self.layer = self.args.layer
        self.resync = self.args.resync
        self.multi_thread = not self.args.single_thread
        if self.args.single_thread:
            self.download_processes = 1
        elif self.args.download_threads:
            self.download_processes = self.args.download_threads
        self.check = self.args.check

    def _get_token(self):
        """ Load the Conductor Api key """
        token_path = os.path.join(os.path.dirname(self.this_file), 'auth', 'CONDUCTOR_TOKEN.pem')
        if not os.path.exists(token_path):
            raise IOError("Could not locate .pem file: %s" % token_path)
        with open(token_path, 'r') as file_obj:
            user = file_obj.read()
        userpass = "%s:unused" % user.rstrip()
        return userpass

    def _auth_service(self):
        """ Get and authorize credentials for google cloud storage """
        credentials = self._get_credentials()
        http = httplib2.Http()
        http = credentials.authorize(http)
        service = discovery.build('storage', submit_settings.API_VERSION, http=http)
        return service

    def _get_credentials(self):
        """ Store and verify the cloud storage credentials """
        storage = oauthfile.Storage(
            os.path.join(
                os.path.dirname(self.this_file),
                'auth',
                'conductor.dat'
                )
            )
        credentials = storage.get()
        if credentials is None or credentials.invalid:
            credentials = tools.run_flow(submit_settings.FLOW, storage, self.args)
        return credentials

    def list_cloud_contents(self, file_prefix, fields_to_return="items(name,md5Hash)"):
        """ Given a cloud storage bucket and prefix, return the files within """
        self.logger.debug("PREFIX: %s", file_prefix)
        req = self.service.objects().list(
            bucket=BUCKET_NAME,
            prefix=file_prefix,
            fields=fields_to_return)
        try:
            resp = req.execute()
        except HttpError, excp:
            self.logger.error("Server failed to respond! %s", excp)
            resp = {}
        if resp == {}:
            file_path = "%s/%s" % (BUCKET_NAME, file_prefix)
            self.logger.info("No Files in storage, skipping. %s", file_path)
            return None
        try:
            cloud_files = resp['items']
        except KeyError, excp:
            self.logger.error("Server Response contains no items! %s", excp)
        return cloud_files

    def calculate_md5(self, path):
        """ Get the base64 encoded md5 hash for a local file """
        with open(path, 'rb') as file_obj:
            contents = file_obj.read()
        binary_hash = hashlib.md5(contents).digest()
        md5_hash = base64.b64encode(binary_hash)
        self.logger.debug("LOCAL MD5: %s", md5_hash)
        return md5_hash

    def download_files(self, download_items):
        """ Iterate over a list of downloads """
        for download in download_items:
            self.download_file(download[0], download[1], download[2])
        self.logger.debug("THREAD TIME: %s", (time.time()-self.start))

    def download_file(self, cloud_source, destination, md5=None, tries=1):
        """ Download and verify a file from cloud storage """
        if tries > 6:
            raise IOError("Failed to download %s to %s" % (cloud_source, destination))
        self.logger.debug("SOURCE: %s", cloud_source)
        self.logger.debug("DESTINATION: %s", destination)
        self.logger.debug("MD5: %s", md5)
        service = self._auth_service() # Have to reauth in the download thread

        self.logger.info("Starting download for %s", destination)
        with open(destination, 'w') as file_obj:
            self.logger.debug("CLOUD SOURCE %s", cloud_source)
            request = service.objects().get_media(bucket=BUCKET_NAME, object=cloud_source)
            dloader = MediaIoBaseDownload(file_obj, request, chunksize=submit_settings.CHUNKSIZE)
            done = False
            while not done:
                status, done = dloader.next_chunk()
                if status:
                    sys.stdout.write("\rDownload %d%%." % int(status.progress() * 100))
                    sys.stdout.flush()

        local_md5 = self.calculate_md5(destination)
        if local_md5 == md5:
            self.logger.debug("Hashes Match!")
        else:
            retry_str = "%s %s" % (md5, local_md5)
            self.logger.debug("Hashes dont match, retry needed %s", retry_str)
            time.sleep(tries*4) # increase sleep times between retries
            self.download_file(cloud_source, destination, md5)

        sys.stdout.write("\n")
        sys.stdout.flush()
        self.logger.info("Download Complete! %s", destination)

    def get_download(self, jid):
        """ Ask the Conductor API for the job info to get the output directory """
        end_url = "jobs/info/%s" % jid
        request_url = "%s/%s" % (CONDUCTOR_URL, end_url)
        handler = self.make_request(request_url)
        file_data = handler.read()
        return file_data

    def make_request(self, url, json_data=None):
        """ Make a basic auth request to the conductor api """
        self.logger.debug("connecting to conductor at: " + url)
        password_manager = urllib2.HTTPPasswordMgrWithDefaultRealm()
        password_manager.add_password(None, url, self.userpass.split(':')[0], 'unused')
        auth = urllib2.HTTPBasicAuthHandler(password_manager)
        opener = urllib2.build_opener(auth)
        urllib2.install_opener(opener)
        req = urllib2.Request(
            url,
            headers={
                'Content-Type':'application/json',
                'Accepts':'application/json'},
            data=json_data)
        handler = urllib2.urlopen(req)
        self.logger.debug("response code was %s", handler.getcode())
        return handler

    def get_destination_dir(self, cloud_source):
        """ Get and make the destination dir based on the source file """
        file_name = cloud_source.split('/')[-1]
        image_src_path = cloud_source.split(self.file_prefix)[-1]
        if "/" in image_src_path:
            sub_dir = "/".join(image_src_path.split('/')[:-1])
        else:
            sub_dir = ""
        resp_dest = self.out_dir
        destination_dir = os.path.join(resp_dest, sub_dir)
        conductor_client_common.make_destination_dir(destination_dir)
        destination = os.path.join(destination_dir, file_name)
        self.logger.debug("destination is: %s", destination)
        self.logger.debug("SubDir: %s", sub_dir)
        return destination

    def start_download_threads(self, files):
        """ Start multiple download threads """
        thread_data = {}
        self.logger.debug(self.download_processes)
        self.logger.info("Getting list of files to download...")
        # Break apart the files into groups for the number of threads
        for i, cloud_file in enumerate(files):
            thread_key = i % self.download_processes
            self.logger.debug(thread_key)
            self.logger.debug("File Info: %s", cloud_file)
            cloud_source = cloud_file["name"]
            if self.layer and self.layer not in cloud_source:
                continue
            src_md5 = cloud_file["md5Hash"]
            destination = self.get_destination_dir(cloud_source)
            if self.resync and not self.precheck_file(destination, src_md5):
                self.logger.info("Local file matches, skipping %s", destination)
                continue
            if thread_data.has_key(thread_key):
                cur_items = thread_data[thread_key]
                cur_items.append((cloud_source, destination, src_md5))
                thread_data[thread_key] = cur_items
            else:
                thread_data[thread_key] = [(cloud_source, destination, src_md5)]

        # Start the threads
        threads = []
        for values in thread_data.values():
            thread_obj = threading.Thread(target=self.download_files, args=[values])
            thread_obj.setDaemon(True)
            threads.append(thread_obj)
            thread_obj.start()

        # Make sure the main thread waits, but new threads stay responsive to cntl-C
        try:
            for thread_obj in threads:
                if thread_obj is not None and thread_obj.isAlive():
                    thread_obj.join(1000)
        except KeyboardInterupt:
            self.logger.error("Ctrl-c received! Sending kill to threads...")
            for thread_obj in threads:
                thread_obj.kill_received = True

    def precheck_file(self, destination, md5):
        """ Check if the file matches local md5 """
        if  os.path.exists(destination):
            self.logger.debug("Comparing local file to cloud...")
            local_md5 = self.calculate_md5(destination)
            if local_md5 == md5:
                self.logger.debug("Files match, skipping download")
                return False
        return True

    def main(self):
        """ Main entry point for app """
        if os.environ.has_key('DEVELOPMENT'):
            self.file_prefix = "dev_files"
            files = self.list_cloud_contents(self.file_prefix)
            self.start_download_threads(files)
            return
        else:
            for job_id in self.job_ids:
                job_id = str(job_id).zfill(5)
                self.file_prefix = "conductor_render/%s/" % job_id
                files = self.list_cloud_contents(self.file_prefix)

                response = self.get_download(job_id)
                resp_data = json.loads(response)
                if not self.out_dir:
                    self.out_dir = "%s/" % resp_data["job"]["output_path"]
                self.logger.debug("OUT_DIR: %s", self.out_dir)
                self.start_download_threads(files)

                if not self.layer:
                    cmd = resp_data["job"]["command"]
                    if "--katana-file" in cmd:
                        self.layer = cmd.split("--render-node=")[-1].split()[0]
                    else:
                        self.layer = ""

                self.start_download_threads(files)
                self.logger.info("Files were downloaded to: %s", self.out_dir)
                self.logger.info("Finished downloading frames for %s", job_id)


if __name__ == "__main__":
    downloader = ConductorDownload()
    downloader.main()
