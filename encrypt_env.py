import getpass
import os
import subprocess
import hashlib

def print_color(text, color):
    print(f"\033[1;{color}m{text}\033[0m")
    
def change_file_permissions(file_path):
    try:
        print_color("Current file permissions are:", "32")
        subprocess.run(['ls', '-l', file_path], check=True)

        os.chmod(file_path, 0o600)

        print_color("Changed file permissions are now:", "32")
        subprocess.run(['ls', '-l', file_path], check=True)
    except Exception as e:
        print("An error occurred while changing file permissions:", str(e))


def encrypt_file(file_path, entered_password=None):
    try:
        if entered_password is None:
            entered_password = get_password()

        with open(file_path, 'rb') as f:
            data = f.read()

        password_bytes = entered_password.encode()

        # Check if the file is already encrypted
        #is_encrypted = all(byte == (byte ^ password_bytes[i % len(password_bytes)]) for i, byte in enumerate(data))
        #if is_encrypted:
        #    print("The file is already encrypted. Skipping encryption.")
        #    return

        encrypted_data = bytearray()
        for i, byte in enumerate(data):
            encrypted_byte = byte ^ password_bytes[i % len(password_bytes)]
            encrypted_data.append(encrypted_byte)

        with open(file_path, 'wb') as f:
            f.write(encrypted_data)

        print_color("File encrypted successfully.", "32")
        print("\n")
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
                # Double Hash the password using SHA256 algorithm
                hashed_password = hash_password(password)
                
                filename = "h_land"
                
                if not os.path.isfile(filename):
                    try:
                        # Create the file if it doesn't exist
                        with open(filename, "w") as f:
                            f.write(hashed_password)
                        
                        # Set file permissions to read and write only for the owner
                        change_file_permissions(filename)
                        return password
                    
                    except IOError as e:
                        error_message = "An error occurred while creating the file: " + str(e)
                        print(error_message)
                        return error_message, ""
                
                else:
                    try:
                        # Append the hashed password to a new line in the existing file
                        command = f"echo -e '\n{hashed_password}' >> {filename}"
                        subprocess.run(["sudo", command], check=True)
                        return password
                    
                    except IOError as e:
                        error_message = "An error occurred while appending to the file: " + str(e)
                        print(error_message)
                        return error_message, ""
                       
        except Exception as e:
            error_message = "An error occurred while getting the password: " + str(e)
            print(error_message)
            return error_message, ""




def hash_password(password):
    # Hash the password using SHA256 algorithm
    hashed_password = hashlib.sha256(password.encode()).hexdigest()
    double_hashed_password = hashlib.sha256(hashed_password.encode()).hexdigest()

    return double_hashed_password


def check_password(entered_password) -> bool:
    # Hash the entered password
    entered_hashed_password = hash_password(entered_password)
    print(entered_hashed_password)

    try:
        # Read the contents of the "h_land" file as root
        command = ["sudo", "cat", "h_land"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        output, error_output = process.communicate()

        if process.returncode == 0:
            hashed_passwords = output.decode().splitlines()
            if entered_hashed_password in hashed_passwords:
                return True
    except Exception as e:
        print(f"Error occurred: {e}")

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
                print("\n")
                return entered_password
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
    print("This file is mean't to be loaded as modules in other scripts")
