"""creates this device's signing key pair once, private key readable only by its owner"""

import os

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

keyDirectory = "/home/pi/gps_timing/keys"
privatePath = os.path.join(keyDirectory, "device_key.pem")
publicPath = os.path.join(keyDirectory, "device_key.pub")

os.makedirs(keyDirectory, exist_ok=True)

if os.path.exists(privatePath):
    print("key already exists at %s, leaving it alone" % privatePath)
    raise SystemExit

privateKey = Ed25519PrivateKey.generate()

privateBytes = privateKey.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
publicBytes = privateKey.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

descriptor = os.open(privatePath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
os.write(descriptor, privateBytes)
os.close(descriptor)

with open(publicPath, "wb") as handle:
    handle.write(publicBytes)

print("private key written to %s, mode 600" % privatePath)
print("public key written to %s, share this one" % publicPath)
