#!/usr/bin/env python3
"""Test SMTP credentials"""

import os
import smtplib
from email.mime.text import MIMEText

# Load from .env
from dotenv import load_dotenv
load_dotenv()

smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
smtp_port = int(os.getenv("SMTP_PORT", "587"))
smtp_user = os.getenv("SMTP_USERNAME")
smtp_pass = os.getenv("SMTP_PASSWORD")
email_from = os.getenv("EMAIL_FROM")
email_to = os.getenv("EMAIL_TO").split(",")[0]

print("=" * 60)
print("SMTP Credential Test")
print("=" * 60)
print(f"Host: {smtp_host}:{smtp_port}")
print(f"Username: {smtp_user}")
print(f"Password: {'*' * len(smtp_pass) if smtp_pass else 'NOT SET'}")
print(f"From: {email_from}")
print(f"To: {email_to}")
print()

try:
    print("Connecting to SMTP server...")
    server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
    print("✓ Connected")

    print("Starting TLS...")
    server.starttls()
    print("✓ TLS started")

    print("Logging in...")
    server.login(smtp_user, smtp_pass)
    print("✓ Login successful!")

    print("Sending test email...")
    msg = MIMEText("This is a test email from arXiv Digest Bot.")
    msg["Subject"] = "[TEST] SMTP Configuration Working"
    msg["From"] = email_from
    msg["To"] = email_to

    server.send_message(msg)
    print("✓ Email sent successfully!")

    server.quit()
    print()
    print("=" * 60)
    print("✓ ALL TESTS PASSED - Your SMTP is configured correctly!")
    print("=" * 60)

except smtplib.SMTPAuthenticationError as e:
    print(f"\n✗ AUTHENTICATION FAILED: {e}")
    print("\nFor Gmail, you need an App Password:")
    print("1. Enable 2-Factor Authentication")
    print("2. Go to: https://myaccount.google.com/apppasswords")
    print("3. Generate 'App Password' for 'Mail'")
    print("4. Use that 16-character password in .env")
    exit(1)

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    exit(1)
