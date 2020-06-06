FROM python:3.7-slim

MAINTAINER Pranav Gupta "pranavgupta4321@gmail.com"

RUN apt-get update -y && \
    apt-get install -y python-pip python-dev

# We copy just the requirements.txt first to leverage Docker cache
COPY ./requirements.txt /app/requirements.txt
WORKDIR /app
COPY . /app

RUN pip install -r requirements.txt

EXPOSE 8899

#ENTRYPOINT [ "python" ]
#CMD [ "app.py" ]
ENTRYPOINT ["python3", "-m", "rqmonitor"]