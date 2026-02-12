# arXiv Digest Bot 📧🤖

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Built with Claude](https://img.shields.io/badge/Built%20with-Claude%20Cowork-7C3AED)](https://claude.ai)

**Automated weekly digest of AI/ML research papers from arXiv, powered by Claude AI.**

Never miss important papers again! This bot fetches papers daily, ranks them by your interests, and sends you a beautifully formatted weekly email digest with AI-generated summaries.

## ✨ Features

- 🔄 **Daily Ingestion**: Fetches papers throughout the week (no missed papers)
- 🎯 **Smart Ranking**: Prioritizes papers matching your keywords
- 🤖 **AI Summaries**: Claude generates concise 2-3 sentence summaries
- 📧 **Beautiful Emails**: HTML digest with paper metadata and direct links
- 👥 **Multiple Recipients**: Share digest with friends and colleagues
- 🚨 **Error Alerts**: Get notified when something goes wrong
- 🐳 **Dockerized**: Runs anywhere, optimized for Raspberry Pi
- ⏰ **Cron-Based**: Lightweight, runs only when needed

## 📋 Prerequisites

- Docker and Docker Compose
- Anthropic API key ([get one here](https://console.anthropic.com/))
- SMTP email account (Gmail, Outlook, etc.)
- Linux/macOS system or Raspberry Pi

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/sidgod/arxiv-digest-bot.git
cd arxiv-digest-bot
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with your settings
nano .env
```

**Required settings:**
- `ANTHROPIC_API_KEY`: Your Claude API key
- `SMTP_*`: Your email server settings
- `EMAIL_TO`: Your email address (or multiple, comma-separated)

**Optional settings:**
- `INTEREST_KEYWORDS`: Keywords for ranking (e.g., `RLHF,fine-tuning,RAG`)
- `ARXIV_CATEGORIES`: Categories to search (default: `cs.AI,cs.CL,cs.LG`)

### 3. Build Docker Image

```bash
docker compose build
```

### 4. Test Manually

```bash
# Test ingest mode (fetch papers)
docker compose run --rm arxiv-digest --mode=ingest

# Test digest mode (send email)
docker compose run --rm arxiv-digest --mode=digest
```

### 5. Setup Cron Jobs

#### On Raspberry Pi / Linux

```bash
# Edit crontab
crontab -e

# Add these lines:
# Daily ingest at midnight
0 0 * * * cd /home/pi/arxiv-digest-bot && /usr/bin/docker compose run --rm arxiv-digest --mode=ingest >> ingest.log 2>&1

# Weekly digest every Monday at 9 AM
0 9 * * 1 cd /home/pi/arxiv-digest-bot && /usr/bin/docker compose run --rm arxiv-digest --mode=digest >> digest.log 2>&1
```

**Important**: Use full paths in crontab!

## 📖 How It Works

### Two-Mode Architecture

**Ingest Mode** (runs daily):
1. Fetches 15 new papers from arXiv
2. Stores in SQLite database (pending queue)
3. Exits (~10 seconds, no API costs)

**Digest Mode** (runs weekly):
1. Loads all pending papers from the week (~70-100 papers)
2. Ranks by keyword match (if configured) or chronologically
3. Selects top 15 papers
4. Generates summaries using Claude AI
5. Sends HTML email digest
6. Clears pending queue

### Why Daily Ingest?

If we only fetch once per week, we'd miss papers uploaded earlier in the week (they get buried under newer submissions). Daily ingestion ensures comprehensive coverage while still delivering a manageable weekly digest.

## ⚙️ Configuration

### arXiv Categories

Common categories you might want:

| Category | Description |
|----------|-------------|
| `cs.AI` | Artificial Intelligence |
| `cs.CL` | Computation and Language (NLP) |
| `cs.LG` | Machine Learning |
| `cs.CV` | Computer Vision |
| `cs.NE` | Neural and Evolutionary Computing |
| `cs.RO` | Robotics |

### Interest Keywords

Papers matching these keywords get ranked higher:

```bash
INTEREST_KEYWORDS=RLHF,fine-tuning,RAG,attention mechanism,prompt engineering,agents
```

Matching logic:
- Title matches: 3 points
- Abstract matches: 1 point each (max 3)
- Case-insensitive, partial matching

### Email Recipients

```bash
# Single recipient
EMAIL_TO=you@example.com

# Multiple recipients (share with friends!)
EMAIL_TO=you@example.com,friend1@example.com,friend2@example.com
```

### Gmail Setup

1. Enable 2-Factor Authentication
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Use App Password in `.env`:

```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-16-char-app-password
EMAIL_FROM=your-email@gmail.com
```

## 🔍 Example Digest Email

```
Subject: [arXiv Digest] Top 15 of 87 Papers - Week of Feb 7

📊 Weekly Summary
• Showing top 15 of 87 papers collected this week
• 🎯 8 papers match your interest keywords
• Collection period: Jan 31 - Feb 7, 2026

┌─────────────────────────────────────────────┐
│ Efficient Fine-Tuning of LLMs via Sparse   │
│ Adapters                                    │
│ arXiv:2402.15432 • Feb 7, 2026             │
│ 🏷️ cs.AI  cs.LG                            │
│ 🎯 Matches: fine-tuning, attention         │
│                                             │
│ This paper introduces a novel sparse        │
│ adapter architecture that reduces           │
│ fine-tuning memory requirements by 80%...   │
└─────────────────────────────────────────────┘

[... 14 more paper cards ...]
```

## 🐛 Troubleshooting

### Check Logs

```bash
# View ingest logs
tail -f ingest.log

# View digest logs
tail -f digest.log

# View application logs
tail -f data/logs/app.log
```

### Common Issues

#### "No new papers" (Exit Code 5)

This is normal if arXiv hasn't published new papers in your categories. Not an error.

#### "SMTP Authentication Failed" (Exit Code 4)

- Verify `SMTP_USERNAME` and `SMTP_PASSWORD`
- For Gmail, use App Password (not regular password)
- Check 2FA is enabled

#### "arXiv API Error" (Exit Code 2)

- Check internet connection
- arXiv may be temporarily down (retry later)
- Rate limiting (script includes automatic retries)

#### "Claude API Error" (Exit Code 3)

- Verify `ANTHROPIC_API_KEY`
- Check API quota/billing
- Claude may be temporarily unavailable

#### "Configuration Error" (Exit Code 1)

- Check `.env` file exists and is readable
- Verify all required fields are set
- Check email format is valid

### Manual Testing

```bash
# Test configuration
docker compose run --rm arxiv-digest --mode=ingest

# Test with fewer papers (faster)
ARXIV_DAILY_FETCH_LIMIT=5 docker compose run --rm arxiv-digest --mode=ingest

# Inspect database
sqlite3 data/digest.db "SELECT COUNT(*) FROM pending_papers;"
sqlite3 data/digest.db "SELECT arxiv_id, title FROM pending_papers LIMIT 5;"
```

### Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | None |
| 1 | Configuration error | Check `.env` file |
| 2 | arXiv API error | Check network, retry later |
| 3 | Claude API error | Check API key and quota |
| 4 | Email sending error | Check SMTP settings |
| 5 | No new papers | Normal, not an error |

## 🏗️ Project Structure

```
arxiv-digest-bot/
├── src/
│   ├── main.py           # Entry point & orchestration
│   ├── config.py         # Configuration management
│   ├── arxiv_scraper.py  # arXiv API client
│   ├── ranker.py         # Keyword-based ranking
│   ├── summarizer.py     # Claude AI integration
│   ├── notifier.py       # Email notifications
│   └── storage.py        # SQLite database
├── data/                 # Database & logs (created automatically)
├── Dockerfile            # Container definition
├── docker-compose.yml    # Docker Compose config
├── requirements.txt      # Python dependencies
├── .env.example          # Example configuration
└── README.md             # This file
```

## 🔐 Security Notes

- **Never commit `.env` file** (contains secrets)
- Database stored locally in `./data`
- Container runs as non-root user
- Secrets passed via environment variables only

## 💰 Cost Estimate

**Claude API**: ~$0.05-0.10 per digest (15 summaries)

- Sonnet 4.5: ~$0.003 per summary
- Haiku 4.5: ~$0.0003 per summary (cheaper but lower quality)

**Weekly cost**: ~$0.05-0.40 depending on model and paper count

## 📈 Future Enhancements

- [ ] Web UI for configuration
- [ ] Per-recipient keyword preferences
- [ ] Slack/Discord/Telegram notifications
- [ ] RSS feed generation
- [ ] Relevance scoring with embeddings
- [ ] Paper recommendation engine
- [ ] Historical digest archive

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

You are free to:
- ✅ Use commercially
- ✅ Modify and distribute
- ✅ Use privately
- ✅ Sublicense

The only requirement is to include the original copyright notice and license in any copy of the software.

## 🙏 Acknowledgments

- [arXiv](https://arxiv.org/) for providing open access to research papers
- [Anthropic](https://www.anthropic.com/) for Claude AI
- Built with ❤️ for the AI/ML research community

## 📧 Support

Having issues? Open a GitHub issue or check the troubleshooting section above.

---

**Happy researching! 🚀📚**
