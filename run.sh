#!/bin/bash

# Update package manager
sudo apt-get update

# Install pip
sudo apt-get install -y python3-pip nginx docker.io docker-compose

# Install requirements from requirements.txt file
pip3 install -r requirements.txt
