import subprocess
import os


def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")


def start_nostpy_relay(tor_flag=None):
    try:
        os.chdir("./docker")
        file_path = "./postgresql/"

        if os.path.exists(file_path):
            subprocess.run(
                ["sudo", "setfacl", "-R", "-m", f"u:{os.getlogin()}:rwx", file_path],
                check=True,
            )
        else:
            print_color("File does not exist. Skipping the command.", "33")

        if tor_flag:
            pwd = os.getcwd()
            print_color(f"Current working directory: {pwd}", "34")
            subprocess.run(
                ["docker-compose", "-f", "docker-compose-tor.yaml", "up", "-d"],
                check=True,
            )
        else:
            subprocess.run(
                ["docker-compose", "-f", "docker-compose.yaml", "up", "-d"], check=True
            )
        os.chdir("..")

    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")
    except Exception as e:
        print_color(f"Unexpected error occurred: {e}", "31")


def destroy_containers_and_images():
    try:
        os.chdir("./docker")
        subprocess.run(["docker-compose", "down"], check=True)

        image_names = [
            "docker_nostr_query:latest",
            "docker_event_handler:latest",
            "docker_websocket_handler:latest",
            "docker_nginx-certbot:latest",
            "redis:latest",
            "postgres:14",
        ]

        for image_name in image_names:
            subprocess.run(
                [
                    "sudo",
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
        subprocess.run(["docker-compose", "down"], check=True)
        os.chdir("..")
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")


def execute_setup_script():
    try:
        subprocess.run(["python3", "build_env.py"], check=True)
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")


def menu():
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
        print_color("2) Start Nostpy relay (Clearnet only)", "32")
        print_color("3) Start Nostpy relay (Clearnet + Tor)", "32")
        print_color("4) Destroy all docker containers and images", "31")
        print_color("5) Stop all containers", "33")
        print_color("6) Exit menu", "31")

        options = {
            "1": execute_setup_script,
            "2": start_nostpy_relay,
            "3": lambda: start_nostpy_relay(tor_flag=True),
            "4": destroy_containers_and_images,
            "5": stop_containers,
            "6": lambda: print_color("Exited menu", "31"),
        }

        try:
            choice = input("\nEnter an option number (1-6): ")
            if choice in options:
                if choice == "6":
                    print_color("Exiting...", "31")
                    break
                else:
                    options[choice]()
            else:
                print_color("Invalid choice. Please enter a valid option number.", "31")
        except ValueError:
            print_color("Invalid input. Please enter a valid option number.", "31")


if __name__ == "__main__":
    menu()
