import getpass
import os
import subprocess
import hashlib
import stat

env_file = './docker_stuff/.env'

def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")
    
def change_file_permissions(file_path):
    try:
        print_color("Current file permissions are:", "32")
        subprocess.run(['ls', '-l', file_path], check=True)

        os.chmod(file_path, 0o640)

        print_color("Changed file permissions are now:", "32")
        subprocess.run(['ls', '-l', file_path], check=True)
    except Exception as e:
        print("An error occurred while changing file permissions:", str(e))


def encrypt_file(file_path):
    try:
        entered_password = get_password()
        with open(file_path, 'rb') as f:
            data = f.read()

        password_bytes = entered_password.encode()

        encrypted_data = bytearray()
        for i, byte in enumerate(data):
            encrypted_byte = byte ^ password_bytes[i % len(password_bytes)]
            encrypted_data.append(encrypted_byte)

        with open(file_path, 'wb') as f:
            f.write(encrypted_data)

        print("File encrypted successfully.")
        print("\nEncrypted content is:")
        subprocess.run(['cat', env_file], check=True)
    except Exception as e:
        print("An error occurred while encrypting the file:", str(e))


def get_password() -> str:
    while True:
        try:
            password = getpass.getpass("Enter password to encrypt your env file: ")
            confirm_password = getpass.getpass("Confirm password: ")

            if password != confirm_password:
                error_message = "Passwords do not match. Please try again."
                return error_message, ""
            else:
                # Hash the password using SHA256 algorithm
                hashed_password = hash_password(password)
                
                filename = "h_land"
                
                if not os.path.isfile(filename):
                    # Create the file if it doesn't exist
                    with open(filename, "w") as f:
                        f.write(hashed_password)
                    
                    # Set file permissions to read and write only for the owner
                    change_file_permissions(filename)
                
                return password
        except Exception as e:
            error_message = "An error occurred while getting the password: " + str(e)
            return error_message, ""

def hash_password(password):
    # Hash the password using SHA256 algorithm
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    # Triple hash the password
    for _ in range(2):
        hashed_password = hashlib.sha256(hashed_password.encode()).hexdigest()

    return hashed_password


def check_password(entered_password) -> bool:
    # Hash the entered password
    entered_hashed_password = hashlib.sha256(entered_password.encode()).hexdigest()
    
    # Read the contents of the "h_land" file
    with open("h_land", "r") as f:
        hashed_passwords = f.read().splitlines()

    # Compare the entered hashed password with the stored hashed passwords
    if entered_hashed_password in hashed_passwords:
        return True
    else:
        return False

def decrypt_file(file_path):
    try:
        while True:
            entered_password = getpass.getpass("Enter password to decrypt file: ")
            if check_password(entered_password):
                with open(file_path, 'rb') as f:
                    encrypted_data = f.read()

                password_bytes = entered_password.encode()
                decrypted_data = bytearray()
                for i, byte in enumerate(encrypted_data):
                    decrypted_byte = byte ^ password_bytes[i % len(password_bytes)]
                    decrypted_data.append(decrypted_byte)

                with open(file_path, 'wb') as f:
                    f.write(decrypted_data)

                print_color("File decrypted successfully.", "32")
                print("\nDecrypted content is:")
                subprocess.run(['cat', env_file], check=True)
                print("\n")
                break
            else:
                print_color("Incorrect password. Please try again.", "31")
    except Exception as e:
        print("An error occurred while decrypting the file:", str(e))

def hash_file(env):
    with open(env, 'rb') as f:
        data = f.read()
        file_hash = hashlib.sha256(data).hexdigest()
        
        print(file_hash)

if __name__ == "__main__":
    try:
        change_file_permissions(env_file)

        #password, hashed_password = get_password()

        hash_file(env_file)
        print_color("\nFile hash before encryption:", "32")
        hash_file(env_file)
        print_color("\nFile hash after encryption:", "32")

        print("\nEncrypting the file...")
        encrypt_file(env_file, password)

        print("\nDecrypting the file...")
        decrypt_file(env_file)

    except Exception as e:
        print("An error occurred:", str(e))
