#!/bin/bash

# Update package manager
sudo apt-get update

# Install pip
sudo apt-get install -y python3-pip nginx docker.io docker-compose pipenv

python3 -m pip install --upgrade pip

# Install requirements from requirements.txt file
pip3 install -r requirements.txt
pipenv install

docker-compose up
