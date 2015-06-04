# Conductor Client #

This is the repo for all the tools that you need to run conductor.

## Installation

You will need to have a CONDUCTOR_TOKEN.pem file before continuing

### Docker Install:

Make sure you already have docker installed before continuing.

Please be sure to set CONDUCTOR_ACCOUNT and /path/to/your/CONDUCTOR_TOKEN.pem correctly in the following commands

#### Run uploader

    docker run -it -e CONDUCTOR_ACCOUNT=your_conductor_account -v /path/to/your/CONDUCTOR_TOKEN.pem:/conductor/auth/CONDUCTOR_TOKEN.pem conductorio/client  /conductor/bin/uploader.py

#### Run downloader

    docker run -it -e CONDUCTOR_ACCOUNT=your_conductor_account -v /path/to/your/CONDUCTOR_TOKEN.pem:/conductor/auth/CONDUCTOR_TOKEN.pem conductorio/client  /conductor/conductor/tools/downloader.py

### Native Install

Make sure that you have python 2.7, pip and git installed.

Get the code:

    git clone https://github.com/AtomicConductor/conductor_client.git
    cd conductor_client

Install dependencies:

    pip install -r requirements.txt

Insert pem file:

    cp /path/to/pemfile auth/CONDUCTOR_TOKEN.pem

Create config.yml with your account:
```
account: your_account_name
```

#### Usage


##### Uploader

    ./bin/uploader


##### Downloader

    ./conductor/tools/downloader.py