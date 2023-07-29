import os
import subprocess
os.system("sudo apt-get update -y")
os.system("sudo apt-get install -y docker-compose nginx certbot python3.10-venv python3-certbot-nginx")

subprocess.run(['python3', '-m', 'venv', 'snmpenv'], check=True)
# Activate the virtual environment and run subsequent commands within it
activate_cmd = '. snmpenv/bin/activate && '
commands = [
    'pip install --upgrade pip',
    'pip install -r requirements.txt',
    'python prepare_server.py'
]
for cmd in commands:
    subprocess.run(['sudo', 'bash', '-c', activate_cmd + cmd], check=True)