import subprocess
import os


def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")


def start_nostpy_relay():
    try:
        os.chdir("./docker")
        file_path = "./postgresql/"

        if os.path.exists(file_path):
            subprocess.run(
                ["sudo", "setfacl", "-R", "-m", "u:relay_service:rwx", file_path],
                check=True,
            )
        else:
            print("File does not exist. Skipping the command.")

        subprocess.run(["ls", "-al"], check=True)
        subprocess.run(["groups", "relay_service"], check=True)
        subprocess.run(
            ["sudo", "-u", "relay_service", "docker-compose", "up", "-d"], check=True
        )
        os.chdir("..")

    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")
    except Exception as e:
        print(f"Error occurred during decryption: {e}")
        return


def destroy_containers_and_images():
    try:
        os.chdir("./docker")
        subprocess.run(
            ["sudo", "-u", "relay_service", "docker-compose", "down"], check=True
        )

        # Delete container images by their name
        image_names = [
            "docker_nostr_query:latest",
            "docker_event_handler:latest",
            "docker_websocket_handler:latest",
            "redis:latest",
            "postgres:latest",
            "datadog/agent:latest",
        ]

        for image_name in image_names:
            subprocess.run(
                [
                    "sudo",
                    "-u",
                    "relay_service",
                    "docker",
                    "image",
                    "rm",
                    "-f",
                    image_name,
                ],
                check=True,
            )
        os.chdir("..")
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")


def stop_containers():
    try:
        os.chdir("./docker")
        subprocess.run(
            ["sudo", "-u", "relay_service", "docker-compose", "down"], check=True
        )
        os.chdir("..")
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")


def switch_branches():
    try:
        branch_name = input("Enter the name of the branch you want to switch to: ")
        subprocess.run(["git", "checkout", branch_name], check=True)
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")


def execute_setup_script():
    try:
        subprocess.run(["python3", "build_env.py"], check=True)
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")


while True:
    print_color(
        "\n##########################################################################################",
        "31",
    )
    print_color(
        """ \n
    ███╗   ██╗ ██████╗ ███████╗████████╗██████╗ ██╗   ██╗
    ████╗  ██║██╔═══██╗██╔════╝╚══██╔══╝██╔══██╗╚██╗ ██╔╝
    ██╔██╗ ██║██║   ██║███████╗   ██║   ██████╔╝ ╚████╔╝ 
    ██║╚██╗██║██║   ██║╚════██║   ██║   ██╔═══╝   ╚██╔╝  
    ██║ ╚████║╚██████╔╝███████║   ██║   ██║        ██║   
    ╚═╝  ╚═══╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝        ╚═╝   
                                                     
    """,
        "34",
    )
    print("\nPlease select an option:\n")
    print_color("1) Execute server setup script", "33")
    print_color("2) Start Nostpy relay", "32")
    print_color("3) Switch branches", "33")
    print_color("4) Destroy all docker containers and images", "31")
    print_color("5) Stop all containers", "33")
    print_color("6) Exit menu", "31")

    options = {
        "1": execute_setup_script,
        "2": start_nostpy_relay,
        "3": switch_branches,
        "4": destroy_containers_and_images,
        "5": stop_containers,
        "6": lambda: print_color("Exited menu", "31"),
    }

    try:
        choice = input("\nEnter an option number (1-6): ")
        if choice in options:
            options[choice]()
            if choice == "6":
                print()
                break
    except ValueError:
        print_color("Invalid choice. Please enter a valid option number.", "31")
