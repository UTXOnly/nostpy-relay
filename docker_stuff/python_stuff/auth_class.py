import base64
import binascii
from os import urandom

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


class Kind4MessageCodec:
    """
    A codec for encrypting and decrypting messages using ECDH (Elliptic Curve Diffie-Hellman)
    for key exchange and AES (Advanced Encryption Standard) in CBC mode for encryption.

    Attributes:
        hex_private_key (str): Hexadecimal string of the private key used for ECDH key exchange.
        hex_public_key (str): Hexadecimal string of the public key used for ECDH key exchange.

    Methods:
        encrypt_message(message: str) -> str:
            Encrypts a plaintext message using AES-CBC encryption with a shared key derived from ECDH key exchange.
            Returns the encrypted message in base64 format followed by the IV in base64 as a query string.

        decrypt_message(encrypted_message_with_iv: str) -> str:
            Decrypts an encrypted message which includes the initialization vector (IV).
            Expects the encrypted message in base64 format with the IV appended as a query string.
            Returns the original plaintext message.
    """

    def __init__(self, hex_private_key, hex_public_key):
        self.hex_private_key = hex_private_key
        self.hex_public_key = hex_public_key
        self.private_key = self._generate_private_key()
        self.public_key = self._generate_public_key()

    def _generate_private_key(self):
        private_key_int = int(self.hex_private_key, 16)
        return ec.derive_private_key(private_key_int, ec.SECP256K1(), default_backend())

    def _generate_public_key(self):
        public_key_bytes = binascii.unhexlify("02" + self.hex_public_key)
        return ec.EllipticCurvePublicKey.from_encoded_point(
            ec.SECP256K1(), public_key_bytes
        )

    def encrypt_message(self, message):
        shared_key = self.private_key.exchange(ec.ECDH(), self.public_key)
        shared_x = shared_key[:32]
        iv = urandom(16)
        cipher = Cipher(
            algorithms.AES(shared_x), modes.CBC(iv), backend=default_backend()
        )
        encryptor = cipher.encryptor()
        padder = padding.PKCS7(algorithms.AES.block_size).padder()
        padded_data = padder.update(message.encode("utf-8")) + padder.finalize()
        encrypted_message = encryptor.update(padded_data) + encryptor.finalize()
        encrypted_message_base64 = base64.b64encode(encrypted_message).decode("utf-8")
        iv_base64 = base64.b64encode(iv).decode("utf-8")
        return f"{encrypted_message_base64}?iv={iv_base64}"

    def decrypt_message(self, encrypted_message_with_iv):
        encrypted_message_base64, iv_base64 = encrypted_message_with_iv.split("?iv=")
        encrypted_message = base64.b64decode(encrypted_message_base64)
        iv = base64.b64decode(iv_base64)
        shared_key = self.private_key.exchange(ec.ECDH(), self.public_key)
        shared_x = shared_key[:32]
        cipher = Cipher(
            algorithms.AES(shared_x), modes.CBC(iv), backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded_plaintext = decryptor.update(encrypted_message) + decryptor.finalize()
        unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
        plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
        return plaintext.decode("utf-8")
