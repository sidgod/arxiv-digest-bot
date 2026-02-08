#!/bin/bash
# Test SMTP credentials using Python

# Auto-detect script location
if [ -f ".env" ]; then
    ENV_FILE=".env"
elif [ -f "../.env" ]; then
    ENV_FILE="../.env"
else
    echo "ERROR: .env file not found"
    exit 1
fi

# Parse .env file safely (only SMTP-related variables)
parse_env() {
    local key=$1
    grep "^${key}=" "$ENV_FILE" | cut -d '=' -f 2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'$//"
}

SMTP_HOST=$(parse_env "SMTP_HOST")
SMTP_PORT=$(parse_env "SMTP_PORT")
SMTP_USERNAME=$(parse_env "SMTP_USERNAME")
SMTP_PASSWORD=$(parse_env "SMTP_PASSWORD")
EMAIL_FROM=$(parse_env "EMAIL_FROM")
EMAIL_TO=$(parse_env "EMAIL_TO")

echo "=========================================="
echo "SMTP Credential Test"
echo "=========================================="
echo "Host: ${SMTP_HOST}:${SMTP_PORT}"
echo "Username: ${SMTP_USERNAME}"
echo "Password: $(echo $SMTP_PASSWORD | sed 's/./*/g')"
echo "Password length: ${#SMTP_PASSWORD} characters"
echo "From: ${EMAIL_FROM}"
echo "To: ${EMAIL_TO}"
echo ""

# Test using Python with better error diagnostics
python3 << PYEOF
import os
import sys
import smtplib
import socket
from email.mime.text import MIMEText

smtp_host = "${SMTP_HOST}" or "smtp.gmail.com"
smtp_port = int("${SMTP_PORT}" or "587")
smtp_user = "${SMTP_USERNAME}"
smtp_pass = "${SMTP_PASSWORD}"
email_from = "${EMAIL_FROM}"
email_to = "${EMAIL_TO}".split(",")[0].strip()

# Validate inputs
if not smtp_user or not smtp_pass:
    print("✗ ERROR: SMTP_USERNAME or SMTP_PASSWORD not set in .env")
    sys.exit(1)

# Check if password looks like an App Password (16 chars, alphanumeric)
password_length = len(smtp_pass)
print(f"Debug: Password has {password_length} characters")
if password_length < 16:
    print("⚠ WARNING: Gmail App Passwords are 16 characters long.")
    print("  Your password is only {password_length} characters - this may not be an App Password.")
    print()

try:
    print("1. Connecting to SMTP server...")
    server = smtplib.SMTP(smtp_host, smtp_port, timeout=30)
    server.set_debuglevel(0)  # Set to 1 for verbose output
    print("   ✓ Connected")

    print("2. Starting TLS...")
    server.starttls()
    print("   ✓ TLS started")

    print("3. Logging in...")
    print(f"   Attempting login as: {smtp_user}")
    try:
        server.login(smtp_user, smtp_pass)
        print("   ✓ Login successful!")
    except smtplib.SMTPAuthenticationError as auth_err:
        print(f"   ✗ Authentication failed: {auth_err}")
        raise

    print("4. Sending test email...")
    msg = MIMEText("This is a test email from arXiv Digest Bot.\\n\\nIf you received this, your SMTP is configured correctly!")
    msg["Subject"] = "[TEST] SMTP Configuration Working"
    msg["From"] = email_from
    msg["To"] = email_to

    server.send_message(msg)
    print("   ✓ Email sent!")

    server.quit()
    print()
    print("=" * 60)
    print("✓ SUCCESS - Check your inbox!")
    print("=" * 60)
    sys.exit(0)

except smtplib.SMTPAuthenticationError as e:
    print()
    print("=" * 60)
    print("✗ AUTHENTICATION FAILED")
    print("=" * 60)
    print(f"Error: {e}")
    print()
    print("For Gmail, you MUST use an App Password:")
    print("   1. Enable 2-Factor Authentication on your Google account")
    print("   2. Go to: https://myaccount.google.com/apppasswords")
    print("   3. Generate 'App Password' for 'Mail'")
    print("   4. Copy the 16-character password (no spaces)")
    print("   5. Use that in your .env file as SMTP_PASSWORD")
    print()
    print("DO NOT use your regular Gmail password!")
    sys.exit(1)

except socket.timeout as e:
    print()
    print("=" * 60)
    print("✗ CONNECTION TIMEOUT")
    print("=" * 60)
    print("The connection timed out during login.")
    print()
    print("Possible causes:")
    print("   1. Wrong password (most common)")
    print("   2. Not using Gmail App Password")
    print("   3. Network/firewall blocking SMTP")
    print("   4. Gmail blocking suspicious login attempts")
    print()
    print("Try these steps:")
    print("   1. Generate a new Gmail App Password")
    print("   2. Update SMTP_PASSWORD in your .env")
    print("   3. Make sure 2FA is enabled on your Gmail account")
    print("   4. Check if your network blocks port 587")
    sys.exit(1)

except Exception as e:
    print()
    print(f"✗ ERROR: {e}")
    print(f"   Type: {type(e).__name__}")
    sys.exit(1)
PYEOF
