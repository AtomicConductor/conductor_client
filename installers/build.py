#!/usr/bin/env python 
import os
import json
import subprocess
import glob

REPO_URL = 'https://github.com/AtomicConductor/conductor_client.git'

payload = json.loads(os.environ['payload'])
release_id = payload["release"]["id"]
release_version = payload["release"]["tag_name"]
(major_version, minor_version, patch_version) = release_version[1:].split('.')
github_token = os.environ['GITHUB_API_TOKEN']

#subprocess.call('curl  -u {} https://api.github.com/repos/AtomicConductor/conductor_client/commits'.format(github_token), shell=True)
def git_clone(url):
    subprocess.check_call(['git','clone',url])
    
def git_checkout(tag):
    subprocess.check_call(['git', 'checkout', 'tags/{}'.format(tag)])

def build_all(installers):
    for installer in installers:
        subprocess.check_call(['{}/build.sh'.format(installer)],
            shell=True,
            env=dict(os.environ,
                    RELEASE_VERSION=release_version,
                    MAJOR_VERSION=major_version,
                    MINOR_VERSION=minor_version,
                    PATCH_VERSION=patch_version)
        )

if __name__ == '__main__':
    git_clone(REPO_URL)
    os.chdir('conductor_client')
    git_checkout(release_version)
    build_all(glob.glob('installers/*'))