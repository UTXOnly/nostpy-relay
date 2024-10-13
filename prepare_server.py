import os
import subprocess
from dotenv import load_dotenv


def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")


dotenv_path = "./docker/.env"
load_dotenv(dotenv_path, override=True)

env_file_path = os.getenv("ENV_FILE_PATH")



try:
    subprocess.check_call(["sudo", "apt", "install", "python3-pip", "-y"])
    print("Pip installed successfully!")
except subprocess.CalledProcessError as e:
    print(f"An error occurred while installing pip: {e}")


try:
    add_user_command = [
        "sudo",
        "adduser",
        "--disabled-password",
        "--gecos",
        "",
        "relay_service",
    ]
    subprocess.run(add_user_command, input=b"\n\n\n\n\n\n\n", check=True)

    add_to_docker_group_command = ["sudo", "usermod", "-aG", "docker", "relay_service"]
    subprocess.run(add_to_docker_group_command, check=True)
except subprocess.CalledProcessError as e:
    print(f"An error occurred while adding the user: {e}")

try:
    change_group_env = ["sudo", "setfacl", "-m", "g:relay_service:r", dotenv_path]
    subprocess.run(change_group_env, check=True)
    add_home_directory_ex = ["sudo", "setfacl", "-m", "g:relay_service:x", r"../"]
    subprocess.run(add_home_directory_ex, check=True)
except subprocess.CalledProcessError as e:
    print(f"An error occurred while changing the group of the file: {e}")
