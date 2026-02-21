import smtplib
import os
import sys

# Credentials from your config
SMTP_SERVER = "smtp.ionos.de"
SMTP_PORT = 587
SMTP_USER = "admin@aethery.cloud"
SMTP_PASSWORD = "Kasd89hinkj/(bjkjk.aAsd%%d98njk$"

try:
    print(f"Connecting to {SMTP_SERVER}:{SMTP_PORT}...")
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.set_debuglevel(1)  # Show detailed communication
    
    print("Starting TLS...")
    server.starttls()
    
    print(f"Logging in as {SMTP_USER}...")
    server.login(SMTP_USER, SMTP_PASSWORD)
    
    print("\n✅ SUCCESS! Credentials are valid.")
    server.quit()
    sys.exit(0)
    
except smtplib.SMTPAuthenticationError as e:
    print(f"\n❌ AUTHENTICATION FAILED: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    sys.exit(1)
