#!/usr/bin/env python

import os
import sys
import urllib2
import subprocess
import traceback
import logging
import json
import imp

try:
    imp.find_module('conductor')
except ImportError, e:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

import conductor
import conductor.setup

CONFIG = conductor.setup.CONFIG
branch = 'master'


class Updater(object):
    def __init__(self):
        self.main()
        exit(0)


    def main(self):
        self.enter_tools_dir()
        self.check_for_git()
        local_revision = self.get_local_revision()
        upstream_revision = self.get_upstream_revision()
        if local_revision == upstream_revision:
            # exit with success if we don't need to update
            logging.info("local client is up to date")
            exit(0)
        logging.info("updating local client")
        self.fetch_code()
        self.ensure_clean_working_tree()
        self.ensure_correct_branch(branch)
        self.update_tools(upstream_revision)
        logging.info('successfully updated client tools to ' + upstream_revision)


    def enter_tools_dir(self):
        base_dir = os.path.dirname(os.path.realpath(__file__))
        logging.debug("changing into dir: " + base_dir)
        os.chdir(base_dir)

    def check_for_git(self):
        # determine if git is installed
        which_git = self.run('which git')
        if which_git[0] == 0:
            logging.debug('git is installed')
        else:
            logging.error('could not find an install of git. Please see:')
            logging.error('\thttp://git-scm.com/book/en/v2/Getting-Started-Installing-Git')
            logging.error('exiting')
            exit(1)

    def get_local_revision(self):
        # get local version
        git_rev_command = self.run('git rev-parse HEAD')
        if git_rev_command[0] != 0:
            logging.error('could not determine local client version: ')
            logging.error(git_rev_command[1])
            logging.error(git_rev_command[2])
            logging.error('exiting')
            exit(1)
        local_rev = git_rev_command[1].strip()
        logging.debug("local_rev is: '%s'" % local_rev)
        return local_rev

    def get_upstream_revision(self):
        client_version_endpoint = os.path.join(CONFIG['url'],'clientref')
        try:
            upstream_response = urllib2.urlopen(client_version_endpoint).read()
            json_response = json.loads(upstream_response)
            upstream_rev = json_response['ref']
            logging.debug("upstream_rev is '%s'" % upstream_rev)
        except ValueError:
            logging.error('response was not in json format. got:')
            logging.error(upstream_response)
            exit(1)
        except KeyError:
            logging.error("response did not have key 'ref':\n\t%s" % json_response)
            exit(1)
        except Exception, e:
            logging.error('could not get client version from app at:')
            logging.error("\t" + client_version_endpoint)
            logging.error(traceback.format_exc())
            logging.error('exiting')
            exit(1)
        return upstream_rev

    def fetch_code(self):
        logging.info('getting new client code')
        status, stdout, stderr = self.run("git fetch origin " + branch )
        if status != 0:
            logging.error('could not update client tools:')
            logging.error(stdout)
            logging.error(stderr)
            logging.error('exiting')
            exit(1)
        return True

    def ensure_clean_working_tree(self):
        status, stdout, stderr = self.run('git status --porcelain')
        if stdout:
            logging.error('working tree is dirty:')
            logging.error(stdout)
            logging.error(stderr)
            logging.error('exiting')
            exit(1)
        else:
            logging.debug('working tree is clean')

    def ensure_correct_branch(self,local_branch):
        # ensure branch is correct
        status, stdout, stderr = self.run('git rev-parse --abbrev-ref HEAD')
        if stdout.strip() != local_branch:
            logging.error("current branch is set to %s, not %s" % (stdout.strip(), local_branch))
            logging.error('exiting')
            exit(1)

    def update_tools(self,upstream_rev):
        status, stdout, stderr = self.run("git checkout -B %s %s" % (branch, upstream_rev))
        if status != 0:
            logging.error('could not deploy new client tools.')
            logging.error('do you have changes in your working tree?:')
            logging.error(stdout)
            logging.error(stderr)
            logging.error('exiting')
            exit(1)

    # TODO: use common run func
    def run(self,cmd):
        logging.debug("about to run command: " + cmd)
        command = subprocess.Popen(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = command.communicate()
        status = command.returncode
        return status, stdout, stderr


if __name__ == '__main__':
    Updater().main()
