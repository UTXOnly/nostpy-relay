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

        os.chmod(file_path, 0o640)

        print_color("Changed file permissions are now:", "32")
        subprocess.run(['ls', '-l', file_path], check=True)
    except Exception as e:
        print("An error occurred while changing file permissions:", str(e))


def encrypt_file(file_path, password):
    try:
        with open(file_path, 'rb') as f:
            data = f.read()

        password_bytes = password.encode()

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

def decrypt_file(file_path):
    try:
        while True:
            password = getpass.getpass("Enter password to decrypt file: ")
            with open(file_path, 'rb') as f:
                encrypted_data = f.read()

            # Check if the entered password matches the password hash
            if check_password(password, hashed_password):
                password_bytes = password.encode()
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



env_file = './.env'

while True:
    try:
        password = getpass.getpass("Enter password: ")
        confirm_password = getpass.getpass("Confirm password: ")

        if password != confirm_password:
            print_color("Passwords do not match. Please try again.", "31")
        else:
            # Hash the password using SHA256 algorithm
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            print_color("Hashed passowrd is: ", "32")
            print(hashed_password)
            break
    except Exception as e:
        print("An error occurred while getting the password:", str(e))

def check_password(password, hashed_password):
    # Hash the input password using SHA256 algorithm
    input_hashed_password = hashlib.sha256(password.encode()).hexdigest()
    
    # Compare the input hashed password with the stored hashed password
    if input_hashed_password == hashed_password:
        return True
    else:
        return False
    
def hash_file(env):
    with open(env, 'rb') as f:
        data = f.read()
        file_hash = hashlib.sha256(data).hexdigest()
        
        print(file_hash)

try:
    change_file_permissions(env_file)


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
