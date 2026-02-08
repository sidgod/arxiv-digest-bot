#!/bin/bash
# Deploy arXiv Digest Bot to Raspberry Pi

set -e  # Exit on error

# Configuration
PI_USER="${PI_USER:-pi}"
PI_HOST="${PI_HOST:-raspberrypi.local}"
PI_DEPLOY_DIR="${PI_DEPLOY_DIR:-/home/pi/arxiv-digest-bot}"

echo "==========================================="
echo "arXiv Digest Bot - Raspberry Pi Deployment"
echo "==========================================="
echo ""
echo "Target: ${PI_USER}@${PI_HOST}:${PI_DEPLOY_DIR}"
echo ""

# Check if we can reach the Pi
echo "1. Testing SSH connection..."
if ! ssh -o ConnectTimeout=5 "${PI_USER}@${PI_HOST}" "echo 'Connection successful'"; then
    echo "ERROR: Cannot connect to ${PI_USER}@${PI_HOST}"
    echo "Please check:"
    echo "  - Raspberry Pi is powered on"
    echo "  - SSH is enabled on Raspberry Pi"
    echo "  - Hostname/IP is correct"
    echo "  - SSH keys are configured (or you have the password)"
    exit 1
fi

# Create directory on Pi
echo ""
echo "2. Creating deployment directory..."
ssh "${PI_USER}@${PI_HOST}" "mkdir -p ${PI_DEPLOY_DIR}"

# Copy files using rsync
echo ""
echo "3. Copying project files..."
rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '*.pyc' \
    --exclude '.env' \
    --exclude 'data/' \
    --exclude 'logs/' \
    --exclude '*.log' \
    ./ "${PI_USER}@${PI_HOST}:${PI_DEPLOY_DIR}/"

# Copy .env if it exists locally
if [ -f .env ]; then
    echo ""
    echo "4. Copying .env file..."
    scp .env "${PI_USER}@${PI_HOST}:${PI_DEPLOY_DIR}/.env"
else
    echo ""
    echo "4. No .env file found locally. You'll need to configure it on the Pi."
fi

# Setup on Raspberry Pi
echo ""
echo "5. Setting up on Raspberry Pi..."
ssh "${PI_USER}@${PI_HOST}" << 'ENDSSH'
cd ~/arxiv-digest-bot

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    echo "Docker installed. You may need to log out and back in."
fi

# Install Docker Compose if not present
if ! command -v docker compose &> /dev/null; then
    echo "Installing Docker Compose..."
    sudo apt-get update
    sudo apt-get install -y docker-compose-plugin
fi

# Create data directory
mkdir -p data logs

# Build Docker image
echo "Building Docker image..."
docker compose build

echo ""
echo "Setup complete!"
ENDSSH

echo ""
echo "==========================================="
echo "✓ Deployment Complete!"
echo "==========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. SSH into your Raspberry Pi:"
echo "   ssh ${PI_USER}@${PI_HOST}"
echo ""
echo "2. Configure .env file (if not already done):"
echo "   cd ${PI_DEPLOY_DIR}"
echo "   nano .env"
echo ""
echo "3. Test the bot:"
echo "   docker compose run --rm arxiv-digest --mode=ingest"
echo "   docker compose run --rm arxiv-digest --mode=digest"
echo ""
echo "4. Setup cron jobs:"
echo "   crontab -e"
echo "   # Add the two cron jobs from README.md"
echo ""
