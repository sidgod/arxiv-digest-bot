# arXiv Digest Bot - Implementation Plan

## Project Overview
An automated containerized service that scrapes arXiv for new AI/LLM papers, generates summaries using Claude API, and delivers weekly digests via email.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Raspberry Pi Host System                  │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Daily Cron (midnight): Ingest Mode                  │   │
│  │  0 0 * * * docker compose run --rm arxiv-digest      │   │
│  │             --mode=ingest                            │   │
│  └────────────────┬─────────────────────────────────────┘   │
│                   │                                           │
│                   ▼                                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Ingest Worker (one-shot, ~10 seconds)                │ │
│  │  1. Fetch 10-15 new papers from arXiv                 │ │
│  │  2. Filter out duplicates                             │ │
│  │  3. Store in pending_papers table                     │ │
│  │  4. Exit (no Claude API, no email)                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│                   Accumulates papers daily...                 │
│                                                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Weekly Cron (Monday 9 AM): Digest Mode              │   │
│  │  0 9 * * 1 docker compose run --rm arxiv-digest      │   │
│  │             --mode=digest                            │   │
│  └────────────────┬─────────────────────────────────────┘   │
│                   │                                           │
│                   ▼                                           │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Digest Generator (one-shot, ~2-3 minutes)            │ │
│  │  1. Load ALL pending papers (50-100 from past week)   │ │
│  │  2. Rank by keyword match score                       │ │
│  │  3. Select top 15                                     │ │
│  │  4. Summarize with Claude API                         │ │
│  │  5. Send email digest                                 │ │
│  │  6. Move papers to processed, clear pending           │ │
│  │  7. Exit                                              │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Persistent Volume (/app/data)                         │ │
│  │  - digest.db (SQLite)                                  │ │
│  │    • pending_papers (staging area)                     │ │
│  │    • processed_papers (history)                        │ │
│  │    • runs (logs)                                       │ │
│  │  - logs/                                               │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## Technology Stack

### Core
- **Language**: Python 3.11+ (best ecosystem for ML/AI tooling)
- **Container**: Docker with multi-stage build
- **Scheduler**: OS-level cron (simple, reliable, Unix-native)

### Key Libraries
- **arXiv API**: `arxiv` (official Python client)
- **Claude API**: `anthropic` (official SDK)
- **Email**: `smtplib` (stdlib) + optional HTML templating with `jinja2`
- **Storage**: `sqlite3` (stdlib, lightweight tracking)
- **Logging**: `logging` (stdlib) with structured output

### Scheduling Approach
- **One-shot execution**: Script runs once and exits (no long-running process)
- **Cron trigger**: Host-level cron invokes container via `docker compose run`
- **Benefits**: Simpler, more reliable, better resource usage, easier debugging

### Alternative Notification Channels (Optional)
- Slack: `slack-sdk`
- Discord: `discord-webhook`
- Telegram: `python-telegram-bot`

## Project Structure

```
arxiv-digest-bot/
├── src/
│   ├── __init__.py
│   ├── main.py                  # Entry point, orchestration
│   ├── config.py                # Configuration management
│   ├── arxiv_scraper.py         # arXiv API interaction
│   ├── ranker.py                # Interest-based ranking (optional)
│   ├── summarizer.py            # Claude API integration
│   ├── notifier.py              # Email/notification service
│   ├── storage.py               # SQLite tracking database
│   └── templates/
│       └── email_template.html  # HTML email template
├── tests/
│   ├── __init__.py
│   ├── test_scraper.py
│   ├── test_summarizer.py
│   └── test_notifier.py
├── Dockerfile                   # Multi-stage build
├── docker-compose.yml           # Easy local testing
├── .dockerignore
├── requirements.txt             # Python dependencies
├── .env.example                 # Example environment variables
├── .gitignore
├── README.md                    # Comprehensive documentation
├── LICENSE                      # MIT or Apache 2.0
└── CHANGELOG.md                 # Version history
```

## Component Breakdown

### 1. Configuration Management (`config.py`)
**Purpose**: Centralized configuration from environment variables with validation

**Environment Variables**:
```bash
# Claude API
ANTHROPIC_API_KEY=sk-ant-xxx

# arXiv Search Parameters
ARXIV_CATEGORIES=cs.AI,cs.CL,cs.LG  # Comma-separated
ARXIV_DAILY_FETCH_LIMIT=15          # Papers to fetch per daily ingest
ARXIV_DISPLAY_LIMIT=15              # Papers to show in weekly digest
ARXIV_SEARCH_QUERY=LLM OR "large language model" OR "neural network"

# Interest-Based Ranking
INTEREST_KEYWORDS=                  # Comma-separated (e.g., "RLHF,fine-tuning,RAG,attention")
                                    # If empty, papers sorted chronologically
                                    # If set, papers ranked by keyword match score

# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-specific-password
EMAIL_FROM=your-email@gmail.com

# Digest recipients (gets weekly paper summaries)
# Supports multiple recipients (comma-separated)
EMAIL_TO=your-email@example.com,friend1@example.com,friend2@example.com
EMAIL_SUBJECT_PREFIX=[arXiv Digest]

# Error notifications recipient (gets failure alerts)
ERROR_EMAIL_TO=ops-alerts@example.com  # Can be same as EMAIL_TO or different
ERROR_EMAIL_ENABLED=true               # Set to false to disable error emails

# Optional: Alternative Notifications
SLACK_WEBHOOK_URL=
DISCORD_WEBHOOK_URL=

# Storage
DATA_DIR=/app/data                  # Mounted volume

# Summarization
CLAUDE_MODEL=claude-sonnet-4-5-20250929
SUMMARY_MAX_TOKENS=150              # Per paper summary
```

### 2. arXiv Scraper (`arxiv_scraper.py`)
**Responsibilities**:
- Query arXiv API with configurable search terms and categories
- Filter papers published since last run
- Extract metadata (title, authors, abstract, arXiv ID, PDF link)
- Handle pagination and rate limiting
- Return structured paper data

**Key Methods**:
```python
class ArxivScraper:
    def __init__(self, categories, max_results, search_query)
    def fetch_new_papers(self, since_date: datetime) -> List[Paper]
    def _build_search_query(self) -> str
```

### 3. Claude Summarizer (`summarizer.py`)
**Responsibilities**:
- Initialize Anthropic client
- Generate concise summaries of paper abstracts
- Extract key contributions and relevance to LLM/AI
- Handle API errors and rate limiting
- Batch processing with progress tracking

**Key Methods**:
```python
class ClaudeSummarizer:
    def __init__(self, api_key: str, model: str, max_tokens: int)
    def summarize_paper(self, paper: Paper) -> str
    def batch_summarize(self, papers: List[Paper]) -> List[PaperWithSummary]
```

### 3a. Paper Ranker (`ranker.py`)
**Responsibilities**:
- Score papers based on interest keywords (if configured)
- Match keywords in title and abstract (case-insensitive, partial matching)
- Sort papers by relevance score
- Track which keywords matched for display

**Key Methods**:
```python
class PaperRanker:
    def __init__(self, interest_keywords: Optional[List[str]])
    def rank_papers(self, papers: List[Paper]) -> List[RankedPaper]
    def _calculate_score(self, paper: Paper) -> Tuple[float, List[str]]
    # Score calculation:
    # - If INTEREST_KEYWORDS set: keyword_match_score (title: 3pts, abstract: 1pt per match)
    # - If empty: use publication date as score (newer = higher)
```

**Behavior**:
- If `INTEREST_KEYWORDS` is empty/None: sorts papers by date (newest first)
- If `INTEREST_KEYWORDS` is set: sorts papers by keyword match score (highest first)
- Returns ALL papers ranked (main.py will slice top N based on DISPLAY_LIMIT)

**Prompt Strategy**:
```
You are summarizing an academic paper for busy AI/ML practitioners.
Paper title: {title}
Abstract: {abstract}

Provide a 2-3 sentence summary that:
1. Explains the main contribution
2. Highlights novel techniques or findings
3. Notes practical applications or implications

Keep it concise and accessible.
```

### 4. Notifier (`notifier.py`)
**Responsibilities**:
- Format digest as HTML email with proper styling
- Send digest emails to multiple recipients (comma-separated)
- Send error notification emails to ops recipient
- Support multiple notification channels (extensible)
- Include direct links to papers and arXiv pages
- Display matched keywords if interest-based ranking is enabled

**Key Methods**:
```python
class EmailNotifier:
    def __init__(self, smtp_config: SMTPConfig, digest_recipients: str, error_recipient: str)
    def send_digest(self, papers: List[RankedPaper], date_range: str)
    def send_error_notification(self, error_details: ErrorDetails)
    def _render_digest_html(self, papers: List[RankedPaper]) -> str
    def _render_error_html(self, error_details: ErrorDetails) -> str
    def _send_email(self, to: str, subject: str, html_body: str)
    def _parse_recipients(self, recipients_str: str) -> List[str]  # Parses comma-separated emails
```

**Multiple Recipients Support**:
```python
def _parse_recipients(self, recipients_str: str) -> List[str]:
    """Parse comma-separated email addresses"""
    return [email.strip() for email in recipients_str.split(',') if email.strip()]

def send_digest(self, papers, date_range):
    """Send digest to all recipients"""
    recipients = self._parse_recipients(self.digest_recipients)

    # Build email
    msg = MIMEMultipart('alternative')
    msg['From'] = self.from_address
    msg['To'] = ', '.join(recipients)  # All recipients visible
    msg['Subject'] = f"{self.subject_prefix} Top {len(papers)} Papers..."

    # Send to all
    server.send_message(msg)
    logger.info(f"Digest sent to {len(recipients)} recipient(s)")
```

**Email Types**:

1. **Digest Email** (to EMAIL_TO):
   - Subject: `[arXiv Digest] Top {display_count} of {total_count} Papers - Week of {date}`
   - HTML body with:
     - Summary statistics (e.g., "Showing top 15 of 87 papers collected this week")
     - Matched papers count if INTEREST_KEYWORDS configured
     - Papers in keyword-match order (or chronological if no keywords)
     - Each paper: Title (linked), arXiv ID, date, categories, matched keywords (if any), summary
     - Footer with configuration details and collection period

2. **Error Email** (to ERROR_EMAIL_TO):
   - Subject: `[arXiv Digest ERROR] {mode} Failed - {date}`
   - HTML body with:
     - Error type and message
     - Exit code and timestamp
     - Context (papers count, config values)
     - Recent log lines (last 50)
     - Suggested next steps
     - Next scheduled run time

### 5. Storage (`storage.py`)
**Responsibilities**:
- Store pending papers (fetched daily, awaiting weekly digest)
- Track processed papers (prevent duplicates)
- Log both ingest and digest runs
- Lightweight SQLite database in mounted volume

**Schema**:
```sql
-- Papers fetched but not yet included in digest
CREATE TABLE pending_papers (
    arxiv_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT NOT NULL,
    categories TEXT NOT NULL,    -- Comma-separated: cs.AI,cs.LG
    published_date DATETIME NOT NULL,
    fetched_at DATETIME NOT NULL,
    arxiv_url TEXT NOT NULL
);

-- Papers already sent in a digest
CREATE TABLE processed_papers (
    arxiv_id TEXT PRIMARY KEY,
    title TEXT,
    processed_at DATETIME NOT NULL,
    digest_date DATETIME NOT NULL,  -- Which digest batch it was in
    included_in_digest BOOLEAN      -- True if in top N, False if just fetched
);

-- Track both ingest and digest runs
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_type TEXT NOT NULL,         -- 'ingest' or 'digest'
    timestamp DATETIME NOT NULL,
    papers_count INTEGER,           -- Fetched (ingest) or Sent (digest)
    status TEXT,                    -- 'success', 'error', 'no_papers'
    error_message TEXT
);
```

**Key Methods**:
```python
class Storage:
    # Pending papers (staging area)
    def add_pending_papers(self, papers: List[Paper])
    def get_all_pending_papers(self) -> List[Paper]
    def clear_pending_papers(self)
    def is_paper_pending_or_processed(self, arxiv_id: str) -> bool

    # Processed papers (history)
    def mark_papers_processed(self, papers: List[Paper], digest_date: datetime, included: List[str])

    # Run tracking
    def log_run(self, run_type: str, papers_count: int, status: str)
```

### 6. Main Application (`main.py`)
**Responsibilities**:
- Support two operation modes: `ingest` and `digest`
- Initialize all components from environment config
- Orchestrate workflows for both modes
- Handle exceptions and logging
- Exit cleanly after completion (one-shot execution)

**Mode Selection**:
```python
# Via command-line argument
python -m src.main --mode=ingest   # Daily paper fetching
python -m src.main --mode=digest   # Weekly digest generation
```

**Ingest Mode Workflow** (runs daily, ~10 seconds):
```python
def ingest_mode():
    1. Load configuration from environment variables
    2. Initialize logger
    3. Fetch ARXIV_DAILY_FETCH_LIMIT papers from arXiv
    4. Filter out papers already in pending_papers or processed_papers
    5. If no new papers: log and exit with code 5
    6. Store new papers in pending_papers table
    7. Log run with type='ingest', count, status
    8. Exit with code 0

    # NO Claude API calls
    # NO email sending
    # Fast and cheap
```

**Digest Mode Workflow** (runs weekly, ~2-3 minutes):
```python
def digest_mode():
    1. Load configuration from environment variables
    2. Initialize logger
    3. Load ALL papers from pending_papers table (accumulated over past week)
    4. If no pending papers: log and exit with code 5
    5. Rank papers by interest keywords
       - If INTEREST_KEYWORDS set: rank by keyword match score
       - If empty: rank by publication date (newest first)
    6. Select top ARXIV_DISPLAY_LIMIT papers after ranking
    7. Batch summarize selected papers using Claude API
    8. Send digest email via configured notifier(s)
    9. Mark ALL pending papers as processed (with flag for top N)
    10. Clear pending_papers table
    11. Log run with type='digest', count, status
    12. Exit with code 0
```

**Main Entry Point**:
```python
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['ingest', 'digest'], required=True)
    args = parser.parse_args()

    if args.mode == 'ingest':
        return ingest_mode()
    elif args.mode == 'digest':
        return digest_mode()

if __name__ == "__main__":
    sys.exit(main())
```

## Implementation Steps

### Phase 1: Core Functionality (MVP)
1. **Setup Project Structure**
   - Initialize Python project with proper package structure
   - Create `requirements.txt` with core dependencies
   - Setup `.gitignore` and `.env.example`

2. **Implement arXiv Scraper**
   - Integrate `arxiv` Python library
   - Implement category and date filtering
   - Add unit tests with mock data

3. **Implement Paper Ranker (Optional)**
   - Keyword matching algorithm (case-insensitive, partial matching)
   - Scoring logic (title vs abstract weights)
   - Sort by relevance score
   - Test with sample papers and keywords

4. **Implement Claude Summarizer**
   - Integrate Anthropic SDK
   - Design effective summarization prompt
   - Add error handling and retries
   - Test with sample abstracts

5. **Implement Storage Layer**
   - SQLite schema and migrations
   - CRUD operations for runs and papers
   - Ensure thread-safety

6. **Implement Email Notifier**
   - SMTP integration
   - HTML email template with Jinja2 (include matched keywords section)
   - Test email rendering and delivery

7. **Implement Error Handling**
   - Configuration validation (fail fast on startup)
   - Retry logic with exponential backoff for all external services
   - Partial failure tolerance (continue on individual paper failures)
   - Structured logging (JSON format for parsing)
   - Proper exit codes for monitoring

8. **Integrate Components in Main**
   - Implement argument parsing for mode selection
   - Wire up ingest mode workflow (fetch → store)
   - Wire up digest mode workflow (load → rank → summarize → send)
   - Add comprehensive error handling throughout
   - Handle "no new papers" case gracefully for both modes

### Phase 2: Containerization
9. **Create Dockerfile**
   - Multi-stage build (builder + runtime)
   - Optimize for Raspberry Pi (ARM64 architecture)
   - Minimize image size
   - Non-root user for security

10. **Create docker-compose.yml**
    - Define service with volume mounts
    - Environment variable configuration
    - Restart policy
    - Resource limits for Raspberry Pi

11. **Test Locally**
    - Build image on laptop
    - Run with test configuration via `docker compose run`
    - Verify volume persistence across runs
    - Test manual invocation multiple times
    - Test error scenarios (bad API key, network issues, etc.)

### Phase 3: Productionization
12. **Setup Cron Integration**
    - Add cron setup instructions to README
    - Create helper script for cron installation
    - Document log rotation strategy
    - Add troubleshooting for cron issues

13. **Write Comprehensive README**
    - Project description and features
    - Prerequisites and setup instructions
    - Configuration guide (including INTEREST_KEYWORDS)
    - Deployment instructions (Raspberry Pi + general)
    - Cron setup examples
    - Troubleshooting guide (error codes, common issues)
    - Contributing guidelines

14. **Add Monitoring & Observability**
    - Structured logging (JSON format)
    - Exit codes for cron monitoring
    - Metrics tracking (papers processed, API calls, errors, matched papers)
    - Optional: Dead man's switch / healthcheck ping

15. **Security Hardening**
    - Secrets management best practices
    - Principle of least privilege
    - Dependency vulnerability scanning
    - `.env` file permissions check

16. **CI/CD Setup (Optional)**
    - GitHub Actions for automated builds
    - Multi-architecture builds (AMD64 + ARM64)
    - Publish to Docker Hub or GHCR

### Phase 4: Enhancements (Post-MVP)
17. **Additional Features**
    - **Advanced Subscription Management**:
      - Recipients list file (easier for many subscribers)
      - Per-user keyword preferences
      - Individual unsubscribe links
      - Subscription confirmation emails
      - Web UI for self-service subscribe/unsubscribe
    - Slack/Discord/Telegram notifications
    - Web UI for configuration and management
    - RSS feed generation
    - Local paper archive/cache
    - Per-recipient digest customization (different keywords per person)

## Configuration Strategy

### Environment Variables
All sensitive and deployment-specific configs via environment variables:
- Validated at startup
- Clear error messages for missing required vars
- Sensible defaults for optional vars

### Docker Deployment

#### Initial Setup
```bash
# Clone repository
cd ~/arxiv-digest-bot

# Configure environment
cp .env.example .env
nano .env  # Edit with your API keys and email settings

# Build container
docker compose build

# Test run manually
docker compose run --rm arxiv-digest
```

#### Cron Configuration on Raspberry Pi

Add to crontab on the **host system** (not in container):

```bash
# Edit crontab
crontab -e

# Daily ingest (midnight) - fetch and store papers
0 0 * * * cd /home/pi/arxiv-digest-bot && /usr/bin/docker compose run --rm arxiv-digest --mode=ingest >> /home/pi/arxiv-digest-bot/ingest.log 2>&1

# Weekly digest (Monday 9 AM) - rank, summarize, and send email
0 9 * * 1 cd /home/pi/arxiv-digest-bot && /usr/bin/docker compose run --rm arxiv-digest --mode=digest >> /home/pi/arxiv-digest-bot/digest.log 2>&1
```

**For Testing**:
```bash
# Test ingest mode manually
docker compose run --rm arxiv-digest --mode=ingest

# Test digest mode manually
docker compose run --rm arxiv-digest --mode=digest

# Run ingest more frequently for testing (every hour)
0 * * * * cd /home/pi/arxiv-digest-bot && /usr/bin/docker compose run --rm arxiv-digest --mode=ingest >> /home/pi/arxiv-digest-bot/ingest.log 2>&1
```

**Cron Schedule Examples**:
- `0 0 * * *` - Daily at midnight (ingest)
- `0 9 * * 1` - Every Monday at 9:00 AM (digest)
- `0 9 * * 5` - Every Friday at 9:00 AM (digest)
- `0 12 * * *` - Daily at noon (could use for daily digest if preferred)

**Important Notes**:
- Use full paths to `docker` and project directory
- Separate log files for ingest and digest for easier debugging
- `--rm` flag removes container after execution
- Ensure `.env` file has correct permissions (readable by cron user)
- Two independent jobs = more resilient (ingest failure doesn't block digest)

### Raspberry Pi Considerations
- Use ARM64 base image: `python:3.11-slim-bookworm`
- Set memory limits in docker-compose (Raspberry Pi 4: 2-4GB)
- Consider using `--platform linux/arm64` for builds
- Store data volume on SD card or USB drive

## Testing Strategy

### Unit Tests
- Mock arXiv API responses
- Mock Claude API responses
- Test email rendering without sending
- Test storage operations with in-memory SQLite

### Integration Tests
- Test full workflow with test credentials
- Use Anthropic's test API keys (if available)
- Send test emails to temporary addresses

### Local Testing

#### Without Docker (Development)
```bash
# Install dependencies
pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your credentials

# Test ingest mode
python -m src.main --mode=ingest

# Test digest mode
python -m src.main --mode=digest

# Check exit code
echo $?  # 0 = success, non-zero = error
```

#### With Docker (Production-like)
```bash
# Build image
docker compose build

# Test ingest mode (fetches papers, stores in pending)
docker compose run --rm arxiv-digest --mode=ingest

# Test digest mode (sends email with pending papers)
docker compose run --rm arxiv-digest --mode=digest

# Full workflow test:
# 1. Run ingest a few times to accumulate papers
docker compose run --rm arxiv-digest --mode=ingest
sleep 5
docker compose run --rm arxiv-digest --mode=ingest
sleep 5
docker compose run --rm arxiv-digest --mode=ingest

# 2. Run digest to see the accumulated papers ranked and sent
docker compose run --rm arxiv-digest --mode=digest

# Check logs
docker compose logs

# Inspect database
sqlite3 /sessions/focused-amazing-maxwell/mnt/arxiv-digest-bot/data/digest.db "SELECT COUNT(*) FROM pending_papers;"
```

## Estimated Development Time
- **Phase 1 (Core)**: 10-14 hours (two-mode architecture adds complexity)
- **Phase 2 (Docker)**: 2-3 hours
- **Phase 3 (Docs & Polish)**: 2-3 hours
- **Total**: ~18-24 hours for MVP

## Error Handling Strategy

### **1. Configuration Validation (Fail Fast)**
```python
def validate_config():
    """Validate all required config at startup"""
    required = ['ANTHROPIC_API_KEY', 'SMTP_HOST', 'EMAIL_TO']
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        logger.error(f"Missing required config: {missing}")
        sys.exit(1)  # Configuration error

    # Validate digest email(s) - supports comma-separated
    digest_emails = [e.strip() for e in EMAIL_TO.split(',') if e.strip()]
    if not digest_emails:
        logger.error("EMAIL_TO is empty")
        sys.exit(1)

    for email in digest_emails:
        if not validate_email(email):
            logger.error(f"Invalid digest email: {email}")
            sys.exit(1)

    logger.info(f"Digest will be sent to {len(digest_emails)} recipient(s)")

    # Error email is optional but validate if provided
    error_email = os.getenv('ERROR_EMAIL_TO')
    if error_email and not validate_email(error_email):
        logger.error(f"Invalid error email: {error_email}")
        sys.exit(1)

    # Default ERROR_EMAIL_TO to EMAIL_TO if not specified
    if not error_email:
        os.environ['ERROR_EMAIL_TO'] = EMAIL_TO
        logger.info(f"ERROR_EMAIL_TO not set, using EMAIL_TO for errors")
```

### **2. arXiv API Error Handling**
```python
class ArxivScraper:
    def fetch_papers(self, max_retries=3):
        for attempt in range(max_retries):
            try:
                results = self.client.query(...)
                return results
            except arxiv.HTTPError as e:
                if e.status == 429:  # Rate limit
                    wait = 2 ** attempt  # Exponential backoff
                    logger.warning(f"Rate limited, waiting {wait}s")
                    time.sleep(wait)
                elif e.status >= 500:  # Server error
                    logger.warning(f"arXiv server error, retry {attempt+1}/{max_retries}")
                    time.sleep(5)
                else:
                    logger.error(f"arXiv API error: {e}")
                    sys.exit(2)  # arXiv API error
            except requests.ConnectionError:
                logger.warning(f"Network error, retry {attempt+1}/{max_retries}")
                time.sleep(10)

        logger.error("arXiv API failed after retries")
        sys.exit(2)
```

### **3. Claude API Error Handling**
```python
class ClaudeSummarizer:
    def summarize_paper(self, paper, max_retries=3):
        for attempt in range(max_retries):
            try:
                response = self.client.messages.create(...)
                return response.content[0].text
            except anthropic.RateLimitError:
                wait = 60 * (attempt + 1)
                logger.warning(f"Claude rate limit, waiting {wait}s")
                time.sleep(wait)
            except anthropic.APIError as e:
                logger.warning(f"Claude API error: {e}, retry {attempt+1}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error in Claude API: {e}")
                if attempt == max_retries - 1:
                    return f"[Summary unavailable: {str(e)[:50]}]"

        return "[Summary unavailable after retries]"

    def batch_summarize(self, papers):
        """Continue on individual failures"""
        results = []
        failed_count = 0

        for paper in papers:
            try:
                summary = self.summarize_paper(paper)
                results.append((paper, summary))
            except Exception as e:
                logger.error(f"Failed to summarize {paper.arxiv_id}: {e}")
                failed_count += 1
                # Continue with remaining papers

        if failed_count > len(papers) * 0.5:  # More than 50% failed
            logger.error(f"Too many failures: {failed_count}/{len(papers)}")
            sys.exit(3)  # Claude API error

        return results
```

### **4. Email Error Handling**
```python
class EmailNotifier:
    def send_digest(self, papers, date_range, max_retries=3):
        for attempt in range(max_retries):
            try:
                server = smtplib.SMTP(self.host, self.port, timeout=30)
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
                server.quit()
                logger.info("Email sent successfully")
                return True
            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP auth failed: {e}")
                sys.exit(4)  # Don't retry auth errors
            except smtplib.SMTPException as e:
                logger.warning(f"SMTP error, retry {attempt+1}: {e}")
                time.sleep(10)
            except socket.timeout:
                logger.warning(f"SMTP timeout, retry {attempt+1}")
                time.sleep(15)
            except Exception as e:
                logger.error(f"Unexpected email error: {e}")
                time.sleep(10)

        logger.error("Failed to send email after retries")
        sys.exit(4)
```

### **5. Database Error Handling**
```python
class Storage:
    def add_pending_papers(self, papers):
        try:
            with self.conn:  # Transaction
                for paper in papers:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO pending_papers ...",
                        paper_data
                    )
        except sqlite3.IntegrityError as e:
            logger.warning(f"Duplicate paper ignored: {e}")
        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                logger.error("Database locked (another process running?)")
            else:
                logger.error(f"Database error: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected database error: {e}")
            sys.exit(1)
```

### **6. Partial Failure Handling**
```python
def digest_mode():
    """Continue on non-critical failures"""
    papers = storage.get_all_pending_papers()

    if not papers:
        logger.info("No pending papers")
        sys.exit(5)

    # Rank papers
    try:
        ranked_papers = ranker.rank_papers(papers)
        top_papers = ranked_papers[:DISPLAY_LIMIT]
    except Exception as e:
        logger.error(f"Ranking failed: {e}, using chronological")
        top_papers = sorted(papers, key=lambda p: p.date)[:DISPLAY_LIMIT]

    # Summarize with partial failure tolerance
    summarized = summarizer.batch_summarize(top_papers)

    if not summarized:
        logger.error("All summarizations failed")
        sys.exit(3)

    # Send email with whatever we have
    notifier.send_digest(summarized, date_range)

    # Always clear pending (even if some failed)
    storage.mark_papers_processed(papers)
    storage.clear_pending_papers()
```

### **7. Logging Strategy**
```python
import logging
import json
from datetime import datetime

# Structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    handlers=[
        logging.FileHandler('/app/data/logs/app.log'),
        logging.StreamHandler()
    ]
)

def log_structured(level, message, **kwargs):
    """Structured JSON logging for easy parsing"""
    log_entry = {
        'timestamp': datetime.utcnow().isoformat(),
        'level': level,
        'message': message,
        **kwargs
    }
    logging.log(getattr(logging, level), json.dumps(log_entry))

# Usage
log_structured('INFO', 'Ingest started', mode='ingest', fetch_limit=15)
log_structured('ERROR', 'arXiv API failed', error=str(e), retry_count=3)
```

### **8. Dead Letter Queue (Optional)**
```python
# For papers that repeatedly fail summarization
CREATE TABLE failed_papers (
    arxiv_id TEXT PRIMARY KEY,
    title TEXT,
    failed_at DATETIME,
    error_message TEXT,
    retry_count INTEGER
);

# Retry failed papers in next digest
```

### **9. Error Notification Emails**
```python
def send_error_notification(mode: str, error: Exception, context: dict):
    """Send email alert when runs fail"""
    if not ERROR_EMAIL_ENABLED:
        return

    error_details = {
        'mode': mode,  # 'ingest' or 'digest'
        'timestamp': datetime.utcnow().isoformat(),
        'error_type': type(error).__name__,
        'error_message': str(error),
        'exit_code': sys.exc_info()[2],  # Exit code
        'context': context,  # Additional context (papers count, etc.)
        'logs': get_recent_logs(50)  # Last 50 log lines
    }

    try:
        notifier.send_error_notification(error_details)
    except Exception as e:
        logger.error(f"Failed to send error notification: {e}")
        # Don't let error notification failure crash the job

# Usage in main workflows
def ingest_mode():
    try:
        # ... ingest logic ...
    except Exception as e:
        logger.error(f"Ingest failed: {e}")
        send_error_notification('ingest', e, {'fetch_limit': FETCH_LIMIT})
        sys.exit(2)

def digest_mode():
    try:
        # ... digest logic ...
    except Exception as e:
        logger.error(f"Digest failed: {e}")
        send_error_notification('digest', e, {'pending_count': len(papers)})
        sys.exit(3)
```

**Error Email Format**:
```
Subject: [arXiv Digest ERROR] Ingest Failed - Feb 7, 2026

┌─────────────────────────────────────────────────┐
│ ⚠️  arXiv Digest Bot Error Report               │
├─────────────────────────────────────────────────┤
│                                                  │
│ Mode: ingest                                     │
│ Time: 2026-02-07 00:15:23 UTC                   │
│ Exit Code: 2 (arXiv API error)                  │
│                                                  │
│ Error: HTTPError 429 - Too Many Requests        │
│                                                  │
│ Context:                                         │
│ • Fetch limit: 15                               │
│ • Retry attempts: 3                             │
│                                                  │
│ Recent Logs:                                     │
│ [00:15:20] INFO: Ingest started                 │
│ [00:15:21] WARN: Rate limited, waiting 2s       │
│ [00:15:23] ERROR: arXiv API failed after retries│
│                                                  │
│ Next Steps:                                      │
│ • Check arXiv API status                        │
│ • Review rate limits                            │
│ • Next ingest attempt: tomorrow at 00:00        │
└─────────────────────────────────────────────────┘
```

### **10. Health Checks (Optional)**
```python
def send_healthcheck_ping():
    """Ping external monitoring service"""
    if HEALTHCHECK_URL:
        try:
            requests.get(HEALTHCHECK_URL, timeout=5)
        except:
            pass  # Don't fail job on healthcheck failure
```

## Potential Challenges & Solutions

### 1. arXiv API Rate Limiting
- **Challenge**: API has rate limits (3 requests/second)
- **Solution**: Implement exponential backoff, batch requests, respect sleep intervals

### 2. Claude API Costs
- **Challenge**: Summarizing 50 papers weekly could add up
- **Solution**:
  - Use Claude Haiku for cost efficiency
  - Implement token counting
  - Add cost estimation in logs
  - Make max_results configurable

### 3. Email Deliverability
- **Challenge**: Emails might go to spam
- **Solution**:
  - Use authenticated SMTP (OAuth2 for Gmail)
  - Implement SPF/DKIM if using custom domain
  - Keep HTML clean and avoid spam triggers

### 4. Raspberry Pi Resource Constraints
- **Challenge**: Limited CPU/memory for batch processing
- **Solution**:
  - Process papers sequentially, not in parallel
  - Implement streaming/chunking
  - Set appropriate resource limits
  - Consider running during off-peak hours

### 5. Persistent State Management
- **Challenge**: Need to track processed papers across restarts
- **Solution**:
  - Use Docker volumes for SQLite database
  - Implement database migrations for schema changes
  - Add backup/restore functionality

## Success Metrics
- ✅ Successfully scrapes arXiv weekly
- ✅ Generates high-quality summaries
- ✅ Delivers digest reliably via email
- ✅ Runs stably on Raspberry Pi for 30+ days
- ✅ Zero manual intervention needed
- ✅ Clear documentation for community adoption
- ✅ Docker image < 200MB
- ✅ Processing time < 5 minutes for 50 papers

## Next Steps
Upon approval, I will:
1. Implement Phase 1 components in order
2. Write comprehensive tests
3. Create Dockerfile optimized for Raspberry Pi
4. Write detailed README with setup instructions
5. Test entire workflow locally
6. Provide deployment guide

## Why Two-Mode Architecture (Ingest + Digest)?

### Problem with Single-Mode Approach:
If fetching only once per week, we'd miss papers uploaded earlier in the week:
```
Monday 9 AM: Fetch 50 most recent papers
↓ Papers from Tuesday arrive
↓ Papers from Wednesday arrive
↓ ...
↓ By Sunday, Monday's papers are buried under 100+ new submissions
❌ Weekly digest only sees most recent 50, misses relevant papers from early week
```

### Solution: Daily Ingest + Weekly Digest

**Daily Ingest (midnight)**:
- Fetches 10-15 papers per day
- Stores in pending_papers staging area
- Fast (~10 seconds), no API costs
- Accumulates 70-100 papers over the week

**Weekly Digest (Monday 9 AM)**:
- Loads ALL 70-100 pending papers
- Ranks by keyword match score
- Selects top 15 most relevant
- Summarizes and sends

### Benefits:
1. **Comprehensive coverage** - Captures papers throughout entire week
2. **Better ranking pool** - 70-100 papers to choose from vs just 50
3. **No missed papers** - Monday papers equal candidates as Sunday papers
4. **Cost efficient** - Daily ingests are free, weekly summarization same cost
5. **Resilient** - Ingest failure doesn't block digest, can recover

### Example Week:
```
Mon 12 AM: Ingest 15 → 15 pending
Tue 12 AM: Ingest 12 → 27 pending
Wed 12 AM: Ingest 14 → 41 pending
Thu 12 AM: Ingest 13 → 54 pending
Fri 12 AM: Ingest 15 → 69 pending
Sat 12 AM: Ingest 10 → 79 pending
Sun 12 AM: Ingest 11 → 90 pending

Mon 9 AM: Digest ranks all 90 → sends top 15 → clears pending
```

## Why Cron-Based Architecture?

### Benefits over Long-Running Scheduler Process:
1. **Simplicity**: No scheduler library needed, fewer dependencies
2. **Reliability**: Cron is battle-tested Unix infrastructure
3. **Resource Efficiency**: Container only runs when needed (2-5 min/week vs 24/7)
4. **Easier Debugging**: Can manually trigger anytime with `docker compose run`
5. **Better Fit for Raspberry Pi**: Minimal memory footprint when idle
6. **Standard Practice**: Follows 12-factor app principles (stateless processes)
7. **Flexibility**: Easy to adjust schedule without rebuilding container
8. **Observable**: Cron logs, exit codes, and standard logging integration

### Exit Codes for Monitoring:
```python
0  - Success (digest sent)
1  - Configuration error
2  - arXiv API error
3  - Claude API error
4  - Email sending error
5  - No new papers (info, not error)
```

Can integrate with monitoring tools (healthchecks.io, Dead Man's Snitch) via cron.

## Finalized Digest Format

**Format Decisions** (confirmed with user):
- ✅ **Email Format**: HTML only (rich formatting, clickable links)
- ✅ **Layout**: Card-based (modern, scannable, mobile-friendly)
- ✅ **Organization**: Chronological (newest first), OR interest-ranked if keywords configured
- ✅ **Per-Paper Details**:
  - Title (linked to arXiv abstract page)
  - arXiv ID (displayed and linked)
  - Publication date
  - Category tags (cs.AI, cs.LG, etc.)
  - Claude's 2-3 sentence summary
  - Matched keywords (if INTEREST_KEYWORDS configured)
- ✅ **Not Included**: Author names, direct PDF links, original abstracts

**Visual Example**:
```
Subject: [arXiv Digest] Top 15 of 87 Papers - Week of Feb 7

┌──────────────────────────────────────────────────────────────┐
│  📊 Weekly Summary                                            │
│  • Showing top 15 of 87 papers collected this week           │
│  • 🎯 8 papers match your interest keywords                  │
│  • Searched: cs.AI, cs.CL, cs.LG                             │
│  • Collection period: Jan 31 - Feb 7, 2026                   │
│                                                                │
│  Papers ranked by keyword relevance:                          │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ Efficient Fine-Tuning of LLMs via Sparse Adapters        ││
│  │ arXiv:2402.15432 • Feb 7, 2026                           ││
│  │ 🏷️ cs.AI, cs.LG                                          ││
│  │ 🎯 Matches: fine-tuning, attention mechanism             ││
│  │                                                           ││
│  │ This paper introduces a novel sparse adapter             ││
│  │ architecture that reduces fine-tuning memory...          ││
│  └──────────────────────────────────────────────────────────┘│
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐│
│  │ RLHF at Scale: Training Large Language Models            ││
│  │ arXiv:2402.14521 • Feb 6, 2026                           ││
│  │ 🏷️ cs.LG, cs.AI                                          ││
│  │ 🎯 Matches: RLHF                                         ││
│  │                                                           ││
│  │ Shares practical insights from applying reinforcement... ││
│  └──────────────────────────────────────────────────────────┘│
│                                                                │
│  [... 13 more papers, ranked by relevance ...]                │
└──────────────────────────────────────────────────────────────┘
```

## Open Questions for Consideration
1. **Summary Length**: 2-3 sentences per paper, or longer?
2. **Notification Channels**: Email only, or also Slack/Discord in future?
3. **Paper Limits**: Daily ingest=15, Display=15 reasonable defaults?
4. **Retention**: Keep processed papers history indefinitely, or purge after N days?
5. **Cron Schedule**: Daily midnight + Monday 9 AM reasonable, or different times?
6. **Keyword Matching**: Case-insensitive + partial matching sufficient?
7. **No Matches**: If no papers match keywords, show top 15 by date anyway?
8. **Ingest Timing**: Midnight optimal, or prefer different time (e.g., 6 AM)?

---

**Ready to proceed with cron-based implementation upon your approval!**
