FROM stackbrew/ubuntu:14.04

RUN apt-get update && apt-get install -y python2.7 python-pip

WORKDIR /conductor
ADD requirements.txt /conductor/requirements.txt
RUN pip install -r requirements.txt
ADD . /conductor
