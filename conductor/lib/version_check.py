import imp
import json
import requests

class VersionCheck(object):

    def __init__(self):
        self._installed_release_info = self._get_installed_release_info()

    def _get_latest_release_info(self):
        """
        Return dictionary describing the latest release of the package.
        See: https://developer.github.com/v3/repos/releases/#get-the-latest-release
        """
        url = self._installed_release_info['repository']['url']
        r = requests.get(url+'/releases/latest')
        return r.json()

    @staticmethod
    def _get_installed_release_info():
        """
        Return dictionary describing the installed release of the package.
        """
        conductor_path = imp.find_module('conductor')[1]
        release_file = conductor_path + '/release.json'
        with open(release_file) as data_file:
            return json.load(data_file)
        
    @property
    def is_latest(self):
        """
        Compare installed version with latest release on GitHub.
        Returns True if check fails for any reason.
        """
        try:
            self._latest_release_info = self._get_latest_release_info()
            if self._installed_release_info['release']['id'] < self._latest_release_info['id']:
                return False
            else:
                return True
        except:
            return True
    
    @property
    def update_url(self):
        """
        Return URL of latest GitHub release.
        """
        try:
            if not self.is_latest:
                return self._latest_release_info['html_url']
            else:
                return None
        except:
            return None
        
