#!/bin/bash
# View application logs with filtering options

# Auto-detect path based on where script is run from
if [ -d "data/logs" ]; then
    LOG_DIR="data/logs"
    INGEST_LOG="ingest.log"
    DIGEST_LOG="digest.log"
elif [ -d "../data/logs" ]; then
    LOG_DIR="../data/logs"
    INGEST_LOG="../ingest.log"
    DIGEST_LOG="../digest.log"
else
    LOG_DIR="data/logs"
    INGEST_LOG="ingest.log"
    DIGEST_LOG="digest.log"
fi

APP_LOG="$LOG_DIR/app.log"

echo "=========================================="
echo "arXiv Digest Bot - Log Viewer"
echo "=========================================="
echo ""

# Check what log to view
case "${1:-app}" in
    app)
        if [ ! -f "$APP_LOG" ]; then
            echo "No application log found at $APP_LOG"
            exit 1
        fi
        echo "Application Log (last 50 lines):"
        echo "========================================"
        tail -50 "$APP_LOG"
        ;;

    ingest)
        if [ ! -f "$INGEST_LOG" ]; then
            echo "No ingest log found at $INGEST_LOG"
            exit 1
        fi
        echo "Ingest Log (last 50 lines):"
        echo "========================================"
        tail -50 "$INGEST_LOG"
        ;;

    digest)
        if [ ! -f "$DIGEST_LOG" ]; then
            echo "No digest log found at $DIGEST_LOG"
            exit 1
        fi
        echo "Digest Log (last 50 lines):"
        echo "========================================"
        tail -50 "$DIGEST_LOG"
        ;;

    errors)
        echo "Recent Errors:"
        echo "========================================"
        if [ -f "$APP_LOG" ]; then
            grep -i "ERROR" "$APP_LOG" | tail -20
        fi
        if [ -f "$INGEST_LOG" ]; then
            grep -i "ERROR" "$INGEST_LOG" | tail -20
        fi
        if [ -f "$DIGEST_LOG" ]; then
            grep -i "ERROR" "$DIGEST_LOG" | tail -20
        fi
        ;;

    all)
        echo "All Recent Logs:"
        echo "========================================"
        [ -f "$APP_LOG" ] && echo "=== Application ===" && tail -20 "$APP_LOG"
        [ -f "$INGEST_LOG" ] && echo "=== Ingest ===" && tail -20 "$INGEST_LOG"
        [ -f "$DIGEST_LOG" ] && echo "=== Digest ===" && tail -20 "$DIGEST_LOG"
        ;;

    *)
        echo "Usage: ./view-logs.sh [app|ingest|digest|errors|all]"
        echo ""
        echo "Examples:"
        echo "  ./view-logs.sh              - View application log"
        echo "  ./view-logs.sh ingest       - View ingest log"
        echo "  ./view-logs.sh digest       - View digest log"
        echo "  ./view-logs.sh errors       - View all errors"
        echo "  ./view-logs.sh all          - View all logs"
        exit 1
        ;;
esac

echo ""
echo "========================================"
echo "Tip: Use 'tail -f' to follow logs in real-time:"
echo "  tail -f $APP_LOG"
echo "========================================"
