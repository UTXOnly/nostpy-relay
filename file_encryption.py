import base64
import getpass
import os
import subprocess

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

MAGIC_NUMBER = b'0xENCRYPTED'

def derive_key(password):
    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            iterations=100000,
            salt=b"",  # No salt is used
            length=32,
            backend=default_backend()
        )
        secret = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return secret
    except Exception as e:
        print(f"Error occurred during key derivation: {e}")
        return e

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

def encrypt_file(filename, key=None):
    if key is None:
        password = getpass.getpass("Enter password to encrypt file: ")
        confirm_password = getpass.getpass("Confirm password: ")
        print_color("BE SURE TO SAVE THIS PASSWORD!!!!!!", "31")
        key = derive_key(password)
        if password != confirm_password:
            error_message = "Passwords do not match. Please try again."
            return error_message, ""

    try:
        with open(filename, "rb") as file:
            data = file.read()

        if data.startswith(MAGIC_NUMBER):
            print(f"{filename} is already encrypted.")
            failure = "failed"
            return failure, ""

        fernet = Fernet(key)
        encrypted_data = bytearray(MAGIC_NUMBER) + fernet.encrypt(data)

        with open(filename, "wb") as file:
            file.write(encrypted_data)

        print(f"{filename} encrypted and saved as {filename}")

    except Exception as e:
        print(f"Error occurred during file encryption: {e}")
        return e, ""

def decrypt_file(encrypted_filename, key=None):
    if key is None:
        password = getpass.getpass("Enter password to decrypt file: ")
        key = derive_key(password)

    try:
        with open(encrypted_filename, "rb") as file:
            encrypted_data = file.read()

        if not encrypted_data.startswith(MAGIC_NUMBER):
            print(f"{encrypted_filename} is not encrypted.")
            return False, key

        encrypted_data = encrypted_data[len(MAGIC_NUMBER):]  # Strip magic number from data

        fernet = Fernet(key)
        decrypted_data = fernet.decrypt(encrypted_data)

        with open(encrypted_filename, "wb") as file:
            file.write(decrypted_data)

        print(f"{encrypted_filename} decrypted and saved as {encrypted_filename}")
        return True, key
    except (InvalidToken, Exception) as e:
        print(f"Error occurred during file decryption: {e}")
        return False, key

def main():
    password = input("Enter your password: ")

    choice = input("Choose an action (encrypt/decrypt): ").lower()

    if choice == "encrypt":
        filename = input("Enter the filename to encrypt: ")
        if filename:
            key = derive_key(password)
            encrypt_file(filename, key)
        else:
            print("Filename cannot be empty.")
    elif choice == "decrypt":
        encrypted_filename = input("Enter the encrypted filename to decrypt: ")
        if encrypted_filename:
            key = derive_key(password)
            decrypt_file(encrypted_filename, key)
        else:
            print("Encrypted filename cannot be empty.")
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()
