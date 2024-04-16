## pull official base image
#FROM python:3.10.7-slim-buster
FROM python:3.9.17-slim-bookworm

EXPOSE 8000

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install system dependencies
RUN apt-get update && apt-get install -y netcat-traditional
RUN apt-get install -y curl

# install dependencies
RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/app/requirements.txt
RUN pip install -r requirements.txt

# Also install gcloud 
# Downloading gcloud package
RUN curl https://dl.google.com/dl/cloudsdk/release/google-cloud-sdk.tar.gz > /tmp/google-cloud-sdk.tar.gz

# Installing the package
RUN mkdir -p /usr/local/gcloud \
  && tar -C /usr/local/gcloud -xvf /tmp/google-cloud-sdk.tar.gz \
  && /usr/local/gcloud/google-cloud-sdk/install.sh

# Adding the package path to local
ENV PATH $PATH:/usr/local/gcloud/google-cloud-sdk/bin

# Now, activate the gcloud service account using credentials in the key file
COPY ./keys/jour-smussend-lynchingres-ocr-d61ee4180f5b.json /usr/src/app/keys/jour-smussend-lynchingres-ocr-d61ee4180f5b.json
RUN gcloud auth activate-service-account --key-file=/usr/src/app/keys/jour-smussend-lynchingres-ocr-d61ee4180f5b.json
# And add it to the env:
ENV GOOGLE_APPLICATION_CREDENTIALS=/usr/src/app/keys/jour-smussend-lynchingres-ocr-d61ee4180f5b.json

# copy project
COPY . /usr/src/app/

# run entrypoint.sh
ENTRYPOINT ["/usr/src/app/entrypoint.sh"]
