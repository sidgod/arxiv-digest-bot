# Utility Scripts

This directory contains debugging and maintenance scripts for the arXiv Digest Bot.

## 📋 Available Scripts

### `db-inspect.sh`
**Database inspector** - View current database state

```bash
./scripts/db-inspect.sh
```

Shows:
- Pending papers count
- Processed papers count
- Recent papers in queue (last 15)
- Papers grouped by category
- Recent runs history

**Use when:** You want a quick overview of what's in the database.

---

### `db-search.sh <keyword>`
**Search papers** - Find papers by keyword

```bash
./scripts/db-search.sh transformer
./scripts/db-search.sh "large language model"
```

Searches paper titles and abstracts for the keyword.

**Use when:** Looking for specific papers in the queue.

---

### `db-export.sh`
**Export to CSV** - Export all tables to CSV files

```bash
./scripts/db-export.sh
```

Creates CSV files in `data/exports/`:
- `pending_papers.csv`
- `processed_papers.csv`
- `runs.csv`

**Use when:** You want to analyze data in Excel or other tools.

---

### `db-clear.sh`
**Reset database** - Clear tables for testing

```bash
./scripts/db-clear.sh
```

Interactive prompt to clear:
- Pending papers only
- Processed papers only
- Run history only
- All tables

**Use when:** Testing or starting fresh.

---

### `view-logs.sh [type]`
**Log viewer** - View application logs

```bash
./scripts/view-logs.sh              # Application log
./scripts/view-logs.sh ingest       # Ingest log
./scripts/view-logs.sh digest       # Digest log
./scripts/view-logs.sh errors       # All errors
./scripts/view-logs.sh all          # All logs
```

**Use when:** Debugging issues or checking recent activity.

---

## 🎯 Common Workflows

### Check Current State
```bash
./scripts/db-inspect.sh
```

### Search for Papers on a Topic
```bash
./scripts/db-search.sh RLHF
./scripts/db-search.sh fine-tuning
```

### Debug Failed Digest
```bash
./scripts/view-logs.sh digest
./scripts/view-logs.sh errors
```

### Export Data for Analysis
```bash
./scripts/db-export.sh
# Open data/exports/pending_papers.csv in Excel
```

### Reset for Testing
```bash
# Clear pending queue
./scripts/db-clear.sh
# Choose: pending

# Re-run ingest
docker compose run --rm arxiv-digest --mode=ingest
```

### Monitor in Real-Time
```bash
# Follow application log
tail -f data/logs/app.log

# Follow digest generation
tail -f digest.log
```

## 📊 Database Schema Quick Reference

### `pending_papers`
Papers fetched but not yet sent in digest
- `arxiv_id` - Paper identifier
- `title` - Paper title
- `abstract` - Paper abstract
- `categories` - arXiv categories
- `published_date` - Publication date
- `fetched_at` - When we fetched it
- `arxiv_url` - Link to paper

### `processed_papers`
Papers that have been sent in a digest
- `arxiv_id` - Paper identifier
- `title` - Paper title
- `processed_at` - When processed
- `digest_date` - Which digest it was in
- `included_in_digest` - Was it in top N? (1=yes, 0=no)

### `runs`
Log of all ingest and digest runs
- `id` - Run ID
- `run_type` - 'ingest' or 'digest'
- `timestamp` - When it ran
- `papers_count` - How many papers
- `status` - 'success', 'error', or 'no_papers'
- `error_message` - Error details if failed

## 🔧 Direct SQLite Commands

```bash
# Open interactive shell
sqlite3 data/digest.db

# Useful queries
.tables                                    # List tables
.schema pending_papers                     # Show table structure
SELECT COUNT(*) FROM pending_papers;       # Count papers
SELECT * FROM runs ORDER BY timestamp DESC LIMIT 5;  # Recent runs
.quit                                      # Exit
```

## 💡 Tips

- All scripts should be run from the project root or scripts directory
- Scripts use relative paths (`../data/digest.db`)
- Make sure database exists before running (run ingest first)
- Use `./scripts/<script-name>` from project root
- Or `cd scripts && ./<script-name>` from scripts directory

## 🚨 Troubleshooting

**"Database not found"**
- Run ingest mode first to create the database
- Check you're in the correct directory

**"Permission denied"**
- Make scripts executable: `chmod +x scripts/*.sh`

**"Command not found: sqlite3"**
- Install SQLite: `brew install sqlite` (macOS) or `apt install sqlite3` (Linux)

## 📝 Adding New Scripts

When adding new utility scripts:
1. Place in `scripts/` directory
2. Make executable: `chmod +x scripts/your-script.sh`
3. Use relative path to data: `../data/`
4. Add documentation here
5. Add to `.gitignore` if it generates temporary files
