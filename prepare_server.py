import os
import subprocess
import encrypt_env
from dotenv import load_dotenv

def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")

dotenv_path = "./docker_stuff/.env"
load_dotenv(dotenv_path, override=True)

domain_name = os.getenv('DOMAIN_NAME')
contact = os.getenv('CONTACT')
hex_pubkey = os.getenv('HEX_PUBKEY')
env_file_path = os.getenv('ENV_FILE_PATH')
nginx_filepath = os.getenv('NGINX_FILE_PATH')

try:
    add_user_command = ["sudo", "adduser", "--disabled-password", "--gecos", "", "relay_service"]
    subprocess.run(add_user_command, input=b'\n\n\n\n\n\n\n', check=True)

    add_to_docker_group_command = ["sudo", "usermod", "-aG", "docker", "relay_service"]
    subprocess.run(add_to_docker_group_command, check=True)
except subprocess.CalledProcessError as e:
    print(f"An error occurred while adding the user: {e}")


try:
    change_group_command = ["sudo", "chgrp", "relay_service", dotenv_path]
    subprocess.run(change_group_command, check=True)
except subprocess.CalledProcessError as e:
    print(f"An error occurred while changing the group of the file: {e}")


if os.path.exists(nginx_filepath):
    try:
        subprocess.run(["rm", nginx_filepath], check=True)
        print_color("File removed successfully.", "32")
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while removing the file: {e}")

nginx_config = f"""
server {{
    server_name {domain_name};

    location / {{
        if ($http_accept ~* "application/nostr\+json") {{
            return 200 '{{"name": "{domain_name}", "description": "NostPy relay v0.2", "pubkey": "{hex_pubkey}", "contact": "{contact}", "supported_nips": [1, 2, 4, 15, 16, 25], "software": "git+https://github.com/UTXOnly/nost-py.git", "version": "0.1"}}';
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

if os.path.exists(nginx_filepath):
    print_color("The default configuration file already exists.", "31")
else:
    try:
        with open(nginx_filepath, "w") as f:
            f.write(nginx_config)
        print_color("The default configuration file has been written successfully.", "32")
    except Exception as e:
        print_color(f"An error occurred while writing the default configuration file: {e}", "31")


try:
    subprocess.run(["sudo", "service", "nginx", "restart"], check=True)
except subprocess.CalledProcessError as e:
    print(f"An error occurred while restarting nginx: {e}")

cert_file_path = f"/etc/letsencrypt/live/{domain_name}/fullchain.pem"

if os.path.isfile(cert_file_path):
    print("The file exists!")
else:
    print("The file doesn't exist!")
    try:
        subprocess.run(["sudo", "certbot", "--nginx", "-d", domain_name, "--non-interactive", "--agree-tos", "--email", contact], check=True)
    except subprocess.CalledProcessError as e:
        print(f"An error occurred while running certbot: {e}")

try:
    subprocess.run(["sudo", "service", "nginx", "restart"], check=True)
except subprocess.CalledProcessError as e:
    print(f"An error occurred while restarting nginx: {e}")

encrypt_env.encrypt_file(env_file_path)
