#!/usr/bin/env python

import imp
import os
import sys



try:
    imp.find_module('conductor')

except:
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))


import conductor, conductor.setup
from conductor.setup import *
from conductor.lib import downloader, api_client


if __name__ == "__main__":
    downloader = downloader.Download()
    downloader.main()
