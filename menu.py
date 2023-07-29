import subprocess
import os

# Function to print colored text to the console
def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")


# Function to start Nostpy relay
def start_nostpy_relay():
    # Change directory and start Docker containers
    os.chdir("./docker_stuff")
    subprocess.run(["sudo", "-u", "relay_service", "docker-compose", "up", "-d"])

# Function to destroy all Docker containers and images
def destroy_containers_and_images():
    # Change directory to the Docker stuff folder
    os.chdir("./docker_stuff")
    subprocess.run(["sudo", "-u", "relay_service", "docker-compose", "down"])
    subprocess.run(["sudo", "-u", "relay_service", "docker", "stop", "relay", "docker_stuff_postgres_1"])
    subprocess.run(["sudo", "-u", "relay_service", "docker", "rm", "relay", "docker_stuff_postgres_1"])
    subprocess.run(["sudo", "-u", "relay_service", "docker", "image", "prune", "-f", "--filter", "label=container=relay"])
    subprocess.run(["sudo", "-u", "relay_service", "docker", "image", "prune", "-f", "--filter", "label=container=docker_stuff_postges_1"])



# Function to switch branches
def switch_branches():
    
    branch_name = input("Enter the name of the branch you want to switch to: ")

    # Change branch
    subprocess.run(["git", "checkout", branch_name])


# Function to execute setup.py script
def execute_setup_script():
    subprocess.run(["python3", "build_env.py"])

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
