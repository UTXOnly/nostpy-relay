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
            "python3-venv",
            "python3-pip",
            "acl",
        ],
        check=True,
    )

    commands = [
        "pip install --upgrade pip",
        "pip install -r requirements.txt",
        "python3 prepare_server.py",
    ]
    for cmd in commands:
        subprocess.run(["sudo", "bash", "-c", cmd], check=True)

except subprocess.CalledProcessError as e:
    print(f"An error occurred while executing the command: {e}")
