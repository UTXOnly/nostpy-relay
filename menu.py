import subprocess
import os
import file_encryption

# Function to print colored text to the console
def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")

# Function to start Nostpy relay
def start_nostpy_relay():
    try:
        success, pass_holder = file_encryption.decrypt_file("./docker_stuff/.env")
        if not success:
            print("Decryption failed, file is not encrypted please encrypt file and rerun command")
            return
        
        os.chdir("./docker_stuff")
        #subprocess.run(["sudo", "setfacl", "-R", "u:relay_service:rwx", "./postgresql" ], check=True)
        subprocess.run(["ls", "-al"], check=True)
        subprocess.run(["groups", "relay_service"], check=True)
        subprocess.run(["sudo", "-u", "relay_service", "docker-compose", "up", "-d"], check=True)
        os.chdir("..")
        
        # Re-encrypt env file to keep it encrypted when not in use
        file_encryption.encrypt_file(filename="./docker_stuff/.env", key=pass_holder)
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")
    except Exception as e:
        print(f"Error occurred during decryption: {e}")
        return

# Function to destroy all Docker containers and images
def destroy_containers_and_images():
    try:
        # Change directory to the Docker stuff folder
        os.chdir("./docker_stuff")
        subprocess.run(["sudo", "-u", "relay_service", "docker-compose", "down"], check=True)

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
            subprocess.run(["sudo", "-u", "relay_service", "docker", "image", "rm", "-f", image_name], check=True)
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
        subprocess.run(["python3", "build_env.py"], check=True)
    except subprocess.CalledProcessError as e:
        print_color(f"Error occurred: {e}", "31")

def decrypt_env():
    while True:
        print_color("\n1) Decrypt file", "32")
        print_color("2) Encrypt file", "31")
        print_color("3) Return to main menu", "33")
        option = input("\nEnter 1 to decrypt, 2 to encrypt the file, or 3 to return to the main menu: \n")
        
        if option == "1":
            print_color("Decrypting your .env file", "32")
            file_encryption.decrypt_file(encrypted_filename="./docker_stuff/.env")
        elif option == "2":
            print_color("Encrypting your .env file", "32")
            file_encryption.encrypt_file(filename="./docker_stuff/.env")
        elif option == "3":
            print_color("Returning to main menu", "31")
        else:
            print_color("Invalid option. Please enter either 1, 2, or 3.", "31")

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
    print_color("5) Decrypt/encrypt .env file to edit", "33")
    print_color("6) Exit menu", "31")

    choice = input("\nEnter an option number (1-6): ")

    if choice == "1":
        execute_setup_script()
    elif choice == "2":
        start_nostpy_relay()      
    elif choice == "3":
        switch_branches()
    elif choice == "4":
        destroy_containers_and_images()
    elif choice == "5":
        decrypt_env()
    elif choice == "6":
        print_color("Exited menu", "31")
        break
    else:
        print_color("Invalid choice. Please enter a valid option number.", "31")
