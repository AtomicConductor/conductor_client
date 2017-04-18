
class Backend:

    headers = {"accept-version": "v1"}

    @classmethod
    def next(cls, account, project=None, location=None, number=1):
        """
        Return the next download (dict), or None if there isn't one.
        """
        path = "downloader/next"
        params = {"account": account, "project": project, "location": location}
        return Backend.get(path, params, headers=cls.headers)

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    @DecDownloaderRetry(run_value=Downloader.STATE_RUNNING, tries=3)
    def touch(cls, id_, bytes_transferred=0, account=None, location=None, project=None):
        path = "downloader/touch/%s" % id_
        kwargs = {"bytes_transferred": bytes_transferred,
                  "account": account,
                  "location": location,
                  "project": project}
        try:
            return Backend.put(path, kwargs, headers=cls.headers)
        except requests.HTTPError as e:
            if e.response.status_code == 410:
                LOGGER.warning("Cannot Touch file %s.  Already finished (not active) (410)", id_)
                return
        raise

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    @DecDownloaderRetry(run_value=Downloader.STATE_RUNNING, tries=3)
    def finish(cls, id_, bytes_downloaded=0, account=None, location=None, project=None):
        path = "downloader/finish/%s" % id_
        LOGGER.debug(path)
        payload = {"bytes_downloaded": bytes_downloaded,
                   "account": account,
                   "location": location,
                   "project": project}
        try:
            return Backend.put(path, payload, headers=cls.headers)
        except requests.HTTPError as e:
            if e.response.status_code == 410:
                LOGGER.warning("Cannot finish file %s.  File not active (410)", id_)
                return
        raise

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    @DecDownloaderRetry(run_value=Downloader.STATE_RUNNING, tries=3)
    def fail(cls, id_, bytes_downloaded=0, account=None, location=None, project=None):
        path = "downloader/fail/%s" % id_
        payload = {"bytes_downloaded": bytes_downloaded,
                   "account": account,
                   "location": location,
                   "project": project}
        try:
            return Backend.put(path, payload, headers=cls.headers)
        except requests.HTTPError as e:
            if e.response.status_code == 410:
                LOGGER.warning("Cannot fail file %s.  File not active (410)", id_)
                return
        raise

    @classmethod
    @common.dec_timer_exit(log_level=logging.DEBUG)
    def bearer_token(cls, token):
        url = cls.make_url("bearer")
        headers = dict(cls.headers)
        headers.update({"authorization": "Token %s" % token})
        result = requests.get(url, headers=headers)
        result.raise_for_status()
        return result.json()["access_token"]

    @classmethod
    @DecAuthorize()
    def get(cls, path, params, headers):
        '''
        Return a list of items
        '''
        url = cls.make_url(path)
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    @classmethod
    @DecAuthorize()
    def put(cls, path, data, headers):
        url = cls.make_url(path)
        response = requests.put(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()

    @classmethod
    @DecAuthorize()
    def post(cls, path, data, headers):
        url = cls.make_url(path)
        response = requests.post(url, data=data, headers=headers)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def make_url(path):
        '''
        TODO: get rid of this hardcoding!!!
        '''
        if path == "bearer":
            config_url = CONFIG.get("url", CONFIG["base_url"])
            return "%s/api/oauth_jwt?scope=user" % config_url

        ip_map = {
            "fiery-celerity-88718.appspot.com": "https://beta-api.conductorio.com",
            "eloquent-vector-104019.appspot.com": "https://dev-api.conductorio.com",
            "atomic-light-001.appspot.com": "https://api.conductorio.com"
        }
        config_url = CONFIG.get("url", CONFIG["base_url"]).split("//")[-1]
        project_url = string.join(config_url.split("-")[-3:], "-")
        if os.environ.get("LOCAL"):
            url_base = "http://localhost:8081"
        else:
            url_base = ip_map[project_url]
        url = "%s/api/v1/fileio/%s" % (url_base, path)
        return url
