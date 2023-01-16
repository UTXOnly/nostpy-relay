#!/bin/bash

BRed='\033[1;31m'
BGreen='\033[1;32m'
NC='\033[0m' # No Color

echo -e "${BGreen}Please enter the subdomain for your relay${NC}"
read domain_name
# Update package manager
sudo apt-get update -y

# Install pip
sudo apt-get install -y python3-pip nginx docker.io docker-compose nginx #pipenv

sudo tee /etc/nginx/sites-available/default <<EOF
server{
    server_name ${domain_name};
    location / {
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header Host \$host;
        proxy_pass http://127.0.0.1:8008;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF

sudo service nginx restart
python3 -m pip install --upgrade pip

# Install requirements from requirements.txt file
pip install -r requirements.txt
#pipenv install
cd ./deocker_stuff
docker-compose up
