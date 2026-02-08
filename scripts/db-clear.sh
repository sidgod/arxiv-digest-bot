#!/bin/bash
# Clear database tables (for testing/debugging)

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

echo "=========================================="
echo "arXiv Digest Bot - Database Reset"
echo "=========================================="
echo ""

# Check if database exists
if [ ! -f "$DB" ]; then
    echo "No database found at $DB"
    exit 0
fi

# Show current counts
echo "Current database state:"
run_sqlite <<'SQL'
.headers on
.mode column
SELECT 'Pending Papers:' as Category, COUNT(*) as Count FROM pending_papers
UNION ALL
SELECT 'Processed Papers:', COUNT(*) FROM processed_papers
UNION ALL
SELECT 'Runs:', COUNT(*) FROM runs;
SQL

echo ""
read -p "What do you want to clear? [pending/processed/runs/all/cancel]: " choice

case "$choice" in
    pending)
        run_sqlite "DELETE FROM pending_papers;"
        echo "✓ Cleared pending_papers table"
        ;;

    processed)
        run_sqlite "DELETE FROM processed_papers;"
        echo "✓ Cleared processed_papers table"
        ;;

    runs)
        run_sqlite "DELETE FROM runs;"
        echo "✓ Cleared runs table"
        ;;

    all)
        read -p "Are you sure? This will clear ALL data. [yes/no]: " confirm
        if [ "$confirm" = "yes" ]; then
            run_sqlite "DELETE FROM pending_papers; DELETE FROM processed_papers; DELETE FROM runs;"
            echo "✓ Cleared all tables"
        else
            echo "Cancelled."
            exit 0
        fi
        ;;

    cancel)
        echo "Cancelled."
        exit 0
        ;;

    *)
        echo "Invalid choice. Cancelled."
        exit 1
        ;;
esac

echo ""
echo "New database state:"
run_sqlite <<'SQL'
.headers on
.mode column
SELECT 'Pending Papers:' as Category, COUNT(*) as Count FROM pending_papers
UNION ALL
SELECT 'Processed Papers:', COUNT(*) FROM processed_papers
UNION ALL
SELECT 'Runs:', COUNT(*) FROM runs;
SQL
