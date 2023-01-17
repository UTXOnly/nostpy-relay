#!/bin/bash
# Use this script if you are weird like me and like to destroy all docker containers and images as soon as you are done with them.
# Stop all running containers
docker stop $(docker ps -aq) -f

# Remove all containers
docker rm $(docker ps -aq) -f

# Remove all images
docker rmi $(docker images -q) -f
