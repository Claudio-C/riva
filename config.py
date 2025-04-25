import os

# SSL Certificate paths
SSL_CERT_FILE = "/etc/letsencrypt/live/avatar.ligagc.com/fullchain.pem"
SSL_KEY_FILE = "/etc/letsencrypt/live/avatar.ligagc.com/privkey.pem"

# Riva server configuration
RIVA_SERVER = os.getenv("RIVA_SERVER", "localhost:50051")

# Flask configuration
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
