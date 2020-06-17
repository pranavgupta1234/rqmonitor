FROM python:3.8-slim

MAINTAINER Pranav Gupta "pranavgupta4321@gmail.com"

RUN apt-get update && apt-get install -y --no-install-recommends \
		gcc \
		libc-dev \
	&& rm -rf /var/lib/apt/lists/*

ADD . /

RUN pip install -r requirements.txt
RUN python3 setup.py develop

EXPOSE 8899

ENTRYPOINT ["python3", "-m", "rqmonitor"]