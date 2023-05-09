import subprocess
import os

# Function to print colored text to the console
def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")


# Function to start Nostpy relay
def start_nostpy_relay():
    # Change directory and start Docker containers
    os.chdir("docker_stuff")
    subprocess.run(["sudo", "docker-compose", "up", "-d"])

# Function to destroy all Docker containers and images


def destroy_containers_and_images():
    # Change directory to the Docker stuff folder
    os.chdir("./docker_stuff")
    subprocess.run(["docker", "stop", "relay", "docker_stuff_postgres_1"])
    subprocess.run(["docker", "rm", "relay", "docker_stuff_postgres_1"])
    subprocess.run(["docker", "image", "prune", "-f", "--filter", "label=container=relay"])
    subprocess.run(["docker", "image", "prune", "-f", "--filter", "label=container=docker_stuff_postges_1"])




# Function to switch branches
def switch_branches():
    
    branch_name = input("Enter the name of the branch you want to switch to: ")

    # Change branch
    subprocess.run(["git", "checkout", branch_name])


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
    print_color("1) Start Nostpy relay", "32")
    print_color("2) Destroy all docker containers and images", "32")
    print_color("3) Switch branches", "31")
    print_color("4) Exit menu", "32")

    choice = input("\nEnter an option number (1-4): ")

    if choice == "1":
        start_nostpy_relay()
    elif choice == "2":
        destroy_containers_and_images()
    elif choice == "3":
        switch_branches()
    elif choice == "4":
        print_color("Exited menu", "31")
        break
    else:
        print_color("Invalid choice. Please enter a valid option number.", "31")