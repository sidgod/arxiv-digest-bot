#!/bin/bash
# Export database tables to CSV files

# Auto-detect path
if [ -f "data/digest.db" ]; then
    DB="data/digest.db"
    DB_PATH="$(pwd)/data/digest.db"
    OUTPUT_DIR="data/exports"
elif [ -f "../data/digest.db" ]; then
    DB="../data/digest.db"
    DB_PATH="$(cd .. && pwd)/data/digest.db"
    OUTPUT_DIR="../data/exports"
else
    DB="data/digest.db"
    DB_PATH="$(pwd)/data/digest.db"
    OUTPUT_DIR="data/exports"
fi

# Function to run sqlite3 (local or via Docker)
run_sqlite() {
    if command -v sqlite3 &> /dev/null; then
        sqlite3 "$DB" "$@"
    else
        # Use Docker with sqlite3
        docker run --rm -v "$DB_PATH:/db.db" -v "$(pwd)/$OUTPUT_DIR:/exports" keinos/sqlite3 sqlite3 /db.db "$@"
    fi
}

mkdir -p "$OUTPUT_DIR"

echo "Exporting database tables to CSV..."
echo "========================================"

# Export pending papers
echo "Exporting pending_papers..."
run_sqlite <<EOF
.headers on
.mode csv
.output $OUTPUT_DIR/pending_papers.csv
SELECT * FROM pending_papers ORDER BY published_date DESC;
.quit
EOF

# Export processed papers
echo "Exporting processed_papers..."
run_sqlite <<EOF
.headers on
.mode csv
.output $OUTPUT_DIR/processed_papers.csv
SELECT * FROM processed_papers ORDER BY processed_at DESC;
.quit
EOF

# Export run history
echo "Exporting runs..."
run_sqlite <<EOF
.headers on
.mode csv
.output $OUTPUT_DIR/runs.csv
SELECT * FROM runs ORDER BY timestamp DESC;
.quit
EOF

echo ""
echo "✓ Export complete!"
echo "Files saved to: $OUTPUT_DIR/"
ls -lh "$OUTPUT_DIR"
