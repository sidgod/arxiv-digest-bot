#!/bin/bash
# Database inspection tool for arXiv Digest Bot

# Auto-detect path based on where script is run from
if [ -f "data/digest.db" ]; then
    DB="data/digest.db"
    DB_PATH="$(pwd)/data/digest.db"
elif [ -f "../data/digest.db" ]; then
    DB="../data/digest.db"
    DB_PATH="$(cd .. && pwd)/data/digest.db"
else
    echo "ERROR: Database not found"
    echo "Looked for: data/digest.db or ../data/digest.db"
    echo "Run ingest mode first to create the database."
    exit 1
fi

# Function to run sqlite3 (local or via Docker)
run_sqlite() {
    if command -v sqlite3 &> /dev/null; then
        sqlite3 "$DB" "$@"
    else
        # Use Docker with sqlite3, pass stdin through
        docker run --rm -i -v "$DB_PATH:/db.db" keinos/sqlite3 sqlite3 /db.db "$@"
    fi
}

echo "=========================================="
echo "arXiv Digest Bot - Database Inspector"
echo "=========================================="
echo ""

run_sqlite <<'SQL'
.headers on
.mode column
.width 15 60 20

SELECT 'Database Overview' as '';
SELECT '==================' as '';
SELECT '' as '';

SELECT 'Pending Papers:' as Metric, COUNT(*) as Value FROM pending_papers
UNION ALL
SELECT 'Processed Papers:', COUNT(*) FROM processed_papers
UNION ALL
SELECT 'Total Runs:', COUNT(*) FROM runs;

SELECT '' as '';
SELECT 'Recent Papers in Queue' as '';
SELECT '======================' as '';
SELECT '' as '';

SELECT
    arxiv_id,
    substr(title, 1, 60) || CASE WHEN length(title) > 60 THEN '...' ELSE '' END as title,
    substr(published_date, 1, 10) as date
FROM pending_papers
ORDER BY published_date DESC
LIMIT 15;

SELECT '' as '';
SELECT 'Papers by Category' as '';
SELECT '==================' as '';
SELECT '' as '';

SELECT
    categories,
    COUNT(*) as count
FROM pending_papers
GROUP BY categories
ORDER BY count DESC
LIMIT 10;

SELECT '' as '';
SELECT 'Recent Runs' as '';
SELECT '===========' as '';
SELECT '' as '';

SELECT
    run_type,
    papers_count,
    status,
    substr(timestamp, 1, 19) as time
FROM runs
ORDER BY timestamp DESC
LIMIT 10;
SQL

echo ""
echo "=========================================="
echo "Commands:"
echo "  ./scripts/db-export.sh           - Export data to CSV"
echo "  ./scripts/db-search.sh <keyword> - Search papers"
echo "  ./scripts/db-clear.sh            - Reset database"
echo "=========================================="
