#!/bin/bash

BRed='\033[1;31m'
BGreen='\033[1;32m'
NC='\033[0m' # No Color

echo -e "${BGreen}Please enter the subdomain for your relay${NC}"
read domain_name

echo -e "${BGreen}Is ${BRed}${domain_name}${BGreen} correct?${NC}"
read answer
if [[ $answer == "yes" || $answer == "y" ]]; then
    echo -e "${BGreen}Moving on...${NC}"
else
    echo -e "${BGreen}Please enter the subdomain for your relay${NC}"
    read domain_name
fi
# Update package manager
sudo apt-get update -y

# Install pip
sudo apt-get install -y python3-pip nginx docker.io docker-compose nginx

sudo tee /etc/nginx/sites-available/default <<EOF
server{
    listen 80;
    listen 443 ssl;
    server_name ${domain_name};
    ssl_certificate /etc/letsencrypt/live/${domain_name}/cert.pem;
    ssl_certificate_key /etc/letsencrypt/live/${domain_name}/privkey.pem;
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
#Create SSL cert, follow prompts
CERT_PATH="/etc/letsencrypt/live/${domain_name}/fullchain.pem"

if [ ! -f $CERT_PATH ]; then
  sudo certbot --nginx -d ${domain_name}
else
  echo "SSL certificate for ${domain_name} already exists."
fi
sudo certbot --nginx -d ${domain_name}
wait
sudo service nginx restart


cd ./docker_stuff
docker-compose up
