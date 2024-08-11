import subprocess

try:
    subprocess.run(["sudo", "apt-get", "update", "-y"], check=True)
    subprocess.run(
        [
            "sudo",
            "apt-get",
            "install",
            "-y",
            "docker-compose",
            "python3.10-venv",
            "acl",
        ],
        check=True,
    )

    subprocess.run(["python3", "-m", "venv", "snmpenv"], check=True)

    # Activate the virtual environment and run subsequent commands within it (runs prepare server script in venv)
    activate_cmd = ". snmpenv/bin/activate && "
    commands = [
        "pip install --upgrade pip",
        "pip install -r requirements.txt",
        "python prepare_server.py",
    ]
    for cmd in commands:
        subprocess.run(["sudo", "bash", "-c", activate_cmd + cmd], check=True)

except subprocess.CalledProcessError as e:
    print(f"An error occurred while executing the command: {e}")
