#!/bin/bash
# Search papers by keyword in title or abstract

# Auto-detect path
if [ -f "data/digest.db" ]; then
    DB="data/digest.db"
    DB_PATH="$(pwd)/data/digest.db"
elif [ -f "../data/digest.db" ]; then
    DB="../data/digest.db"
    DB_PATH="$(cd .. && pwd)/data/digest.db"
else
    DB="data/digest.db"
    DB_PATH="$(pwd)/data/digest.db"
fi

# Function to run sqlite3 (local or via Docker)
run_sqlite() {
    if command -v sqlite3 &> /dev/null; then
        sqlite3 "$DB" "$@"
    else
        # Use Docker with sqlite3
        docker run --rm -v "$DB_PATH:/db.db" keinos/sqlite3 sqlite3 /db.db "$@"
    fi
}

if [ $# -eq 0 ]; then
    echo "Usage: ./db-search.sh <keyword>"
    echo "Example: ./db-search.sh transformer"
    exit 1
fi

KEYWORD="$1"

echo "Searching for: $KEYWORD"
echo "========================================"
echo ""

run_sqlite <<SQL
.headers on
.mode column
.width 15 70 12

SELECT
    arxiv_id,
    title,
    substr(published_date, 1, 10) as date
FROM pending_papers
WHERE title LIKE '%$KEYWORD%' OR abstract LIKE '%$KEYWORD%'
ORDER BY published_date DESC;
SQL

echo ""
echo "Search complete."
