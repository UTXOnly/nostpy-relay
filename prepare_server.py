import os
import subprocess
from dotenv import load_dotenv
def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")

dotenv_path = "./docker_stuff/.env"
load_dotenv(dotenv_path)

domain_name=os.getenv('DOMAIN_NAME')
contact=os.getenv('CONTACT')
hex_pubkey=os.getenv('HEX_PUBKEY')
# Install required packages
#os.system("sudo apt-get update -y")
#os.system("sudo apt-get install -y docker-compose nginx certbot python3-certbot-nginx")

default_conf = "/etc/nginx/sites-available/default"

if os.path.exists(default_conf):
    os.system("sudo rm -rf {}".format(default_conf))

# Create a new user
#os.system("sudo adduser relay_service")

# Add the user to the docker group
#os.system("sudo usermod -aG docker realy_service")

# Log out the user to realize the change
#os.system("pkill -KILL -u relay_service")


nginx_config = f"""
server {{
    server_name {domain_name};

    location / {{
        if ($http_accept ~* "application/nostr\+json") {{
            return 200 '{{"name": "{domain_name}", "description": "NostPy relay v0.1", "pubkey": "{hex_pubkey}", "contact": "{contact}", "supported_nips": [1, 2, 4, 15, 16, 25], "software": "git+https://github.com/UTXOnly/nost-py.git", "version": "0.1"}}';
            add_header 'Content-Type' 'application/json';
        }}
    
        add_header 'Access-Control-Allow-Origin' '*';
        add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS';
        add_header 'Access-Control-Allow-Headers' 'DNT,X-CustomHeader,Keep-Alive,User-Agent,X-Requested-With,If-Modified-Since,Cache-Control,Content-Type,Authorization';
        add_header 'Content-Type' 'application/json';
    
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
        proxy_pass http://127.0.0.1:8008;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
}}
"""

# Write nginx config file to disk
with open(f"/etc/nginx/sites-available/default", "w") as f:
    f.write(nginx_config)

os.system("sudo service nginx restart")

file_path = "/etc/letsencrypt/live/nostpy.lol/fullchain.pem"

if os.path.isfile(file_path):
    print("The file exists!")
else:
    print("The file doesn't exist!")
    os.system(f"sudo certbot --nginx -d {domain_name} --non-interactive --agree-tos --email {contact}")


os.system("sudo service nginx restart")

