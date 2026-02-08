# Raspberry Pi Deployment Guide

## Prerequisites

### On Your Local Machine
- SSH access to Raspberry Pi
- `rsync` installed (usually pre-installed on macOS/Linux)
- Project configured with `.env` file

### On Your Raspberry Pi
- Raspberry Pi OS (Bullseye or newer)
- SSH enabled
- Internet connection

## Option 1: Automated Deployment (Recommended)

### 1. Configure Deployment Settings

```bash
# Set these environment variables (or use defaults)
export PI_USER=pi                           # Default: pi
export PI_HOST=192.168.1.100               # Or raspberrypi.local
export PI_DEPLOY_DIR=/home/pi/arxiv-digest-bot  # Default
```

### 2. Run Deployment Script

```bash
./deploy.sh
```

This script will:
- ✅ Test SSH connection
- ✅ Create deployment directory
- ✅ Copy all project files
- ✅ Install Docker and Docker Compose (if needed)
- ✅ Build Docker image
- ✅ Setup data directories

### 3. Complete Setup on Raspberry Pi

```bash
# SSH into your Pi
ssh pi@raspberrypi.local

# Navigate to project
cd ~/arxiv-digest-bot

# Configure environment (if .env wasn't copied)
nano .env
# Add your API keys and email settings

# Test ingest mode
docker compose run --rm arxiv-digest --mode=ingest

# Test digest mode
docker compose run --rm arxiv-digest --mode=digest

# Setup cron jobs
crontab -e
```

Add these lines to crontab:
```bash
# Daily ingest at midnight
0 0 * * * cd /home/pi/arxiv-digest-bot && /usr/bin/docker compose run --rm arxiv-digest --mode=ingest >> ingest.log 2>&1

# Weekly digest every Monday at 9 AM
0 9 * * 1 cd /home/pi/arxiv-digest-bot && /usr/bin/docker compose run --rm arxiv-digest --mode=digest >> digest.log 2>&1
```

## Option 2: Manual Deployment

### 1. Copy Files to Raspberry Pi

```bash
# From your local machine
rsync -avz --progress \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude 'data/' \
    ./ pi@raspberrypi.local:/home/pi/arxiv-digest-bot/

# Copy .env separately (contains secrets)
scp .env pi@raspberrypi.local:/home/pi/arxiv-digest-bot/.env
```

### 2. SSH into Raspberry Pi

```bash
ssh pi@raspberrypi.local
cd ~/arxiv-digest-bot
```

### 3. Install Docker

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo apt-get update
sudo apt-get install -y docker-compose-plugin

# Log out and back in for group changes
exit
```

SSH back in and continue:

```bash
ssh pi@raspberrypi.local
cd ~/arxiv-digest-bot
```

### 4. Build and Test

```bash
# Create directories
mkdir -p data logs

# Build Docker image
docker compose build

# Test ingest mode
docker compose run --rm arxiv-digest --mode=ingest

# Test digest mode
docker compose run --rm arxiv-digest --mode=digest
```

### 5. Setup Cron

```bash
crontab -e
```

Add:
```bash
# Daily ingest at midnight
0 0 * * * cd /home/pi/arxiv-digest-bot && /usr/bin/docker compose run --rm arxiv-digest --mode=ingest >> ingest.log 2>&1

# Weekly digest every Monday at 9 AM
0 9 * * 1 cd /home/pi/arxiv-digest-bot && /usr/bin/docker compose run --rm arxiv-digest --mode=digest >> digest.log 2>&1
```

## Option 3: Git-Based Deployment

If you've pushed to GitHub:

```bash
# SSH into Raspberry Pi
ssh pi@raspberrypi.local

# Clone repository
git clone https://github.com/yourusername/arxiv-digest-bot.git
cd arxiv-digest-bot

# Create .env file
cp .env.example .env
nano .env  # Add your keys

# Follow steps 3-5 from Option 2
```

## Troubleshooting

### Cannot Connect via SSH

```bash
# Test connection
ping raspberrypi.local

# If ping fails, find IP address
# On the Raspberry Pi (connect monitor/keyboard):
hostname -I

# Then use IP directly
ssh pi@192.168.1.100
```

### SSH Key Setup (Optional but Recommended)

```bash
# Generate SSH key (if you don't have one)
ssh-keygen -t ed25519

# Copy to Raspberry Pi
ssh-copy-id pi@raspberrypi.local

# Now you can SSH without password
```

### Docker Permission Denied

```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in
exit
ssh pi@raspberrypi.local
```

### Low Disk Space

```bash
# Check disk space
df -h

# Clean up Docker
docker system prune -a

# Check logs size
du -sh ~/arxiv-digest-bot/logs
```

### ARM64 Build Issues

The Dockerfile is already optimized for ARM64, but if you have issues:

```bash
# Explicitly specify platform
docker compose build --platform linux/arm64
```

## Updating the Bot

### Update from Local Machine

```bash
# Make changes locally, then redeploy
./deploy.sh
```

### Update from Git

```bash
# SSH into Raspberry Pi
ssh pi@raspberrypi.local
cd ~/arxiv-digest-bot

# Pull latest changes
git pull

# Rebuild
docker compose build

# Test
docker compose run --rm arxiv-digest --mode=ingest
```

## Monitoring

### View Logs

```bash
# SSH into Pi
ssh pi@raspberrypi.local
cd ~/arxiv-digest-bot

# View cron logs
tail -f ingest.log
tail -f digest.log

# View application logs
tail -f data/logs/app.log

# View all logs
tail -f *.log data/logs/*.log
```

### Check Cron Status

```bash
# List cron jobs
crontab -l

# View cron log
grep CRON /var/log/syslog

# Test cron job manually
cd /home/pi/arxiv-digest-bot && docker compose run --rm arxiv-digest --mode=ingest
```

### Database Inspection

```bash
# SSH into Pi
ssh pi@raspberrypi.local
cd ~/arxiv-digest-bot

# Count pending papers
sqlite3 data/digest.db "SELECT COUNT(*) FROM pending_papers;"

# View recent papers
sqlite3 data/digest.db "SELECT arxiv_id, title FROM pending_papers LIMIT 5;"

# View run history
sqlite3 data/digest.db "SELECT * FROM runs ORDER BY timestamp DESC LIMIT 10;"
```

## Security Best Practices

1. **Use SSH Keys** instead of passwords
2. **Change default Pi password**: `passwd`
3. **Keep system updated**: `sudo apt update && sudo apt upgrade`
4. **Restrict .env permissions**: `chmod 600 .env`
5. **Enable UFW firewall** (optional):
   ```bash
   sudo apt install ufw
   sudo ufw allow ssh
   sudo ufw enable
   ```

## Performance Tips

1. **Use Haiku model** for lower costs (edit .env):
   ```bash
   CLAUDE_MODEL=claude-haiku-4-5-20251001
   ```

2. **Reduce fetch limits** if needed:
   ```bash
   ARXIV_DAILY_FETCH_LIMIT=10
   ARXIV_DISPLAY_LIMIT=10
   ```

3. **Log rotation** (prevent disk fill):
   ```bash
   # Add to crontab
   0 0 * * 0 find /home/pi/arxiv-digest-bot -name "*.log" -mtime +30 -delete
   ```

## Need Help?

- Check README.md for general troubleshooting
- View logs in `data/logs/app.log`
- Check cron logs in `ingest.log` and `digest.log`
- Open a GitHub issue if you find bugs
