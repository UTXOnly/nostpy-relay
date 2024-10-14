import subprocess
import os


def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")


def run_docker_compose(tor_flag=None, command="up", detach=True):
    """Run docker-compose with appropriate file based on tor_flag"""
    docker_compose_file = "docker-compose.yaml" if not tor_flag else "docker-compose-tor.yaml"
    
    cmd = ["docker-compose", "-f", docker_compose_file, command]
    
    if command == "up" and detach:
        cmd.append("-d")  # Add -d only for 'up' command if detaching
    
    subprocess.run(cmd, check=True)


def start_nostpy_relay(tor_flag=None):
    """Start the relay based on clearnet or tor flag"""
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

        pwd = os.getcwd()
        print_color(f"Current working directory: {pwd}", "34")

        run_docker_compose(tor_flag=tor_flag, command="up", detach=True)
        os.chdir("..")

    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")
    except Exception as e:
        print_color(f"Unexpected error occurred: {e}", "31")


def destroy_containers_and_images(tor_flag=None):
    """Destroy containers and images based on clearnet or tor flag"""
    try:
        os.chdir("./docker")
        
        run_docker_compose(tor_flag=tor_flag, command="down", detach=False)

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


def stop_containers(tor_flag=None):
    """Stop the running containers"""
    try:
        os.chdir("./docker")
        run_docker_compose(tor_flag=tor_flag, command="down", detach=False)
        os.chdir("..")
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")


def execute_setup_script():
    try:
        subprocess.run(["python3", "build_env.py"], check=True)
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")

def manual_wot_run():
    try:
        subprocess.run(["python3", "./docker/nostpy_relay/wot_builder.py"], check=True)
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")


def menu():

    try:

        tor_address = subprocess.run(
            ["sudo", "cat","./docker/tor/data/hidden_service/hostname"],
            check=True,
            capture_output=True,
            text=True
        )
    except:
        tor_address = None
        print("Tor has not been initialized yet")
        
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

        if tor_address:
            print_color(f"Your tor .onion address is: ws://{tor_address.stdout.strip()}", "31")
        print("\nPlease select an option:\n")
        print_color("1) Execute server setup script", "33")
        print_color("2) Manually build Web of Trust", "33")
        print_color("3) Start Nostpy relay (Clearnet only)", "32")
        print_color("4) Start Nostpy relay (Clearnet + Tor)", "32")
        print_color("5) Destroy all docker containers and images (Clearnet)", "31")
        print_color("6) Destroy all docker containers and images (Clearnet + Tor)", "31")
        print_color("7) Stop all containers (Clearnet)", "33")
        print_color("8) Stop all containers (Clearnet + Tor)", "33")
        print_color("9) Exit menu", "31")

        options = {
            "1": execute_setup_script,
            "2": manual_wot_run,
            "3": lambda: start_nostpy_relay(tor_flag=False),
            "4": lambda: start_nostpy_relay(tor_flag=True),
            "5": lambda: destroy_containers_and_images(tor_flag=False),
            "6": lambda: destroy_containers_and_images(tor_flag=True),
            "7": lambda: stop_containers(tor_flag=False),
            "8": lambda: stop_containers(tor_flag=True),
            "9": lambda: print_color("Exited menu", "31"),
        }

        try:
            choice = input("\nEnter an option number (1-8): ")
            if choice in options:
                if choice == "8":
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
