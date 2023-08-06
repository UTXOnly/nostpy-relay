import subprocess
import os
import encrypt_env
import getpass

# Function to print colored text to the console
def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")


# Function to start Nostpy relay
def start_nostpy_relay():
    try:
        # Change directory and start Docker containers
        
        
        encrypt_env.decrypt_file("./docker_stuff/.env")
        os.chdir("./docker_stuff")
        subprocess.run(["ls", "-al"])
        subprocess.run(["groups", "relay_service"])
        subprocess.run(["sudo", "-u", "relay_service", "docker-compose", "up", "-d"])
        os.chdir("..")
        #re-encrypt env file to keep it encrypted when not in use
        encrypt_env.encrypt_file("./docker_stuff/.env")
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")

# Function to destroy all Docker containers and images
def destroy_containers_and_images():
    try:
        # Change directory to the Docker stuff folder
        os.chdir("./docker_stuff")
        subprocess.run(["sudo", "-u", "relay_service", "docker-compose", "down"])

        # Delete container images by their name
        image_names = [
            "docker_stuff_nostr_query:latest",
            "docker_stuff_event_handler:latest",
            "docker_stuff_websocket_handler:latest",
            "redis:latest",
            "postgres:latest",
            "datadog/agent:latest",
        ]

        for image_name in image_names:
            subprocess.run(["sudo", "-u", "relay_service", "docker", "image", "rm", "-f", image_name])
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")

# Function to switch branches
def switch_branches():
    try:
        branch_name = input("Enter the name of the branch you want to switch to: ")

        # Change branch
        subprocess.run(["git", "checkout", branch_name], check=True)
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")

# Function to execute setup.py script
def execute_setup_script():
    try:
        #os.chdir("./docker_stuff")
        subprocess.run(["python3", "build_env.py"])
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")

while True:
    print_color("\n##########################################################################################", "31")
    print_color(""" \n
    
    ███╗   ██╗ ██████╗ ███████╗████████╗██████╗ ██╗   ██╗
    ████╗  ██║██╔═══██╗██╔════╝╚══██╔══╝██╔══██╗╚██╗ ██╔╝
    ██╔██╗ ██║██║   ██║███████╗   ██║   ██████╔╝ ╚████╔╝ 
    ██║╚██╗██║██║   ██║╚════██║   ██║   ██╔═══╝   ╚██╔╝  
    ██║ ╚████║╚██████╔╝███████║   ██║   ██║        ██║   
    ╚═╝  ╚═══╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝        ╚═╝   
                                                     
    
    """ , "34")
    print("\nPlease select an option:\n")
    print_color("1) Execute server setup script", "33")
    print_color("2) Start Nostpy relay", "32")
    print_color("3) Switch branches", "33")
    print_color("4) Destroy all docker containers and images", "31")
    print_color("5) Exit menu", "31")

    choice = input("\nEnter an option number (1-5): ")

    if choice == "1":
        execute_setup_script()
    elif choice == "2":
        start_nostpy_relay()      
    elif choice == "3":
        switch_branches()
    elif choice == "4":
        destroy_containers_and_images()
    elif choice == "5":
        print_color("Exited menu", "31")
        break
    else:
        print_color("Invalid choice. Please enter a valid option number.", "31")

