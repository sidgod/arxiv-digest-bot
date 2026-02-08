"""Main application entry point for arXiv Digest Bot."""

import argparse
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

from src.arxiv_scraper import ArxivScraper
from src.config import Config
from src.notifier import EmailNotifier, ErrorDetails
from src.ranker import PaperRanker
from src.storage import Storage
from src.summarizer import ClaudeSummarizer


def setup_logging(data_dir: str) -> None:
    """Configure structured logging."""
    log_dir = Path(data_dir) / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / "app.log"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )


def get_recent_logs(data_dir: str, lines: int = 50) -> list:
    """Get recent log lines for error reporting."""
    try:
        log_file = Path(data_dir) / "logs" / "app.log"
        if log_file.exists():
            with open(log_file) as f:
                return f.readlines()[-lines:]
        return ["No log file found"]
    except Exception as e:
        return [f"Error reading logs: {e}"]


def send_error_notification(
    notifier: EmailNotifier, mode: str, error: Exception, context: dict, data_dir: str
) -> None:
    """Send error notification email."""
    error_details = ErrorDetails(
        mode=mode,
        timestamp=datetime.utcnow().isoformat(),
        error_type=type(error).__name__,
        error_message=str(error),
        exit_code=getattr(error, "code", 1),
        context=context,
        logs=get_recent_logs(data_dir),
    )

    try:
        notifier.send_error_notification(error_details)
    except Exception as e:
        logging.error(f"Failed to send error notification: {e}")


def ingest_mode(config: Config) -> int:
    """
    Ingest mode: Fetch papers and store in pending queue.

    Returns:
        Exit code (0=success, 2=error, 5=no papers)
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("INGEST MODE - Starting daily paper fetch")
    logger.info("=" * 60)

    # Initialize components
    storage = Storage(f"{config.data_dir}/digest.db")
    scraper = ArxivScraper(config.arxiv_categories, config.arxiv_search_query)
    notifier = EmailNotifier(
        config.smtp_host,
        config.smtp_port,
        config.smtp_username,
        config.smtp_password,
        config.email_from,
        config.email_to,
        config.notification_email_to,
        config.email_subject_prefix,
        config.notification_email_prefix,
        config.notifications_enabled,
    )

    try:
        # Get last successful ingest time to only fetch newer papers
        last_ingest_time = storage.get_last_successful_ingest_time()

        if last_ingest_time:
            logger.info(f"Last successful ingest: {last_ingest_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            logger.info("No previous ingest found, fetching recent papers")

        # Fetch papers (only those published after last ingest)
        try:
            papers = scraper.fetch_papers(config.arxiv_daily_fetch_limit, since_date=last_ingest_time)
        except TimeoutError as e:
            logger.error(f"arXiv API timeout: {e}")
            storage.log_run("ingest", 0, "error", "arXiv API timeout")
            send_error_notification(notifier, "ingest", e, {"error": "arXiv API timeout"}, config.data_dir)
            raise SystemExit(2)

        if not papers:
            logger.info("No new papers found since last ingest")
            storage.log_run("ingest", 0, "no_papers")

            # Send notification even when no papers found (so user knows it ran)
            notifier.send_success_notification("ingest", {
                "Papers Fetched": 0,
                "Status": "No new papers since last run",
                "Categories": ", ".join(config.arxiv_categories),
                "Last Ingest": last_ingest_time.strftime('%Y-%m-%d %H:%M') if last_ingest_time else "First run",
            })

            return 5

        # Filter out already processed/pending papers (defensive check)
        new_papers = [p for p in papers if not storage.is_paper_pending_or_processed(p.arxiv_id)]

        if not new_papers:
            logger.info(f"All {len(papers)} papers already in database, nothing new to add")
            storage.log_run("ingest", 0, "no_papers")

            # Send notification (papers were fetched but already in DB)
            notifier.send_success_notification("ingest", {
                "Papers Fetched": 0,
                "Status": f"All {len(papers)} papers already in database",
                "Categories": ", ".join(config.arxiv_categories),
                "Last Ingest": last_ingest_time.strftime('%Y-%m-%d %H:%M') if last_ingest_time else "First run",
            })

            return 5

        # Add to pending
        added_count = storage.add_pending_papers(new_papers)

        storage.log_run("ingest", added_count, "success")
        logger.info(f"✓ Ingest completed: {added_count} new papers added to pending queue")

        # Send success notification
        notifier.send_success_notification("ingest", {
            "Papers Fetched": added_count,
            "Total Pending": len(new_papers),
            "Categories": ", ".join(config.arxiv_categories),
            "Last Ingest": last_ingest_time.strftime('%Y-%m-%d %H:%M') if last_ingest_time else "First run",
        })

        return 0

    except SystemExit as e:
        storage.log_run("ingest", 0, "error", str(e))
        raise

    except Exception as e:
        logger.error(f"Unexpected error in ingest mode: {e}", exc_info=True)
        storage.log_run("ingest", 0, "error", str(e))
        send_error_notification(notifier, "ingest", e, {}, config.data_dir)
        raise SystemExit(2)

    finally:
        storage.close()


def digest_mode(config: Config) -> int:
    """
    Digest mode: Rank pending papers, summarize top N, and send digest.

    Returns:
        Exit code (0=success, 3=Claude error, 4=email error, 5=no papers)
    """
    logger = logging.getLogger(__name__)
    logger.info("=" * 60)
    logger.info("DIGEST MODE - Starting weekly digest generation")
    logger.info("=" * 60)

    # Initialize components
    storage = Storage(f"{config.data_dir}/digest.db")
    ranker = PaperRanker(config.interest_keywords)
    summarizer = ClaudeSummarizer(config.anthropic_api_key, config.claude_model, config.summary_max_tokens)
    notifier = EmailNotifier(
        config.smtp_host,
        config.smtp_port,
        config.smtp_username,
        config.smtp_password,
        config.email_from,
        config.email_to,
        config.notification_email_to,
        config.email_subject_prefix,
        config.notification_email_prefix,
        config.notifications_enabled,
    )

    try:
        # Load pending papers
        pending_papers = storage.get_all_pending_papers()

        if not pending_papers:
            logger.info("No pending papers to process")
            storage.log_run("digest", 0, "no_papers")

            # Send notification even when no papers (so user knows it ran)
            notifier.send_success_notification("digest", {
                "Papers Summarized": 0,
                "Status": "No pending papers to process",
                "Recipients": len(config.email_to),
                "Keywords Configured": len(config.interest_keywords) if config.interest_keywords else 0,
            })

            return 5

        logger.info(f"Processing {len(pending_papers)} pending papers")

        # Rank papers
        try:
            ranked_papers = ranker.rank_papers(pending_papers)
        except Exception as e:
            logger.error(f"Ranking failed: {e}, falling back to chronological order")
            # Fallback to chronological
            from src.ranker import RankedPaper

            ranked_papers = [
                RankedPaper(paper=p, score=p.published_date.timestamp(), matched_keywords=[])
                for p in pending_papers
            ]
            ranked_papers.sort(key=lambda x: x.score, reverse=True)

        # Check if any papers matched (after strict keyword filtering)
        if not ranked_papers:
            logger.info(f"No papers matched interest keywords from {len(pending_papers)} pending papers")
            storage.log_run("digest", 0, "no_matches")

            # Still mark papers as processed so they don't accumulate
            storage.mark_papers_processed(pending_papers, datetime.utcnow(), [])
            storage.clear_pending_papers()

            # Send notification (so user knows why no digest was sent)
            notifier.send_success_notification("digest", {
                "Papers Summarized": 0,
                "Status": f"No papers matched keywords from {len(pending_papers)} pending",
                "Recipients": len(config.email_to),
                "Keywords": ", ".join(config.interest_keywords) if config.interest_keywords else "None",
            })

            return 5

        # Select top N
        top_papers = ranked_papers[: config.arxiv_display_limit]
        logger.info(f"Selected top {len(top_papers)} papers for digest")

        # Summarize
        summarized = summarizer.batch_summarize(top_papers)

        if not summarized:
            logger.error("All summarization attempts failed")
            storage.log_run("digest", 0, "error", "All summarizations failed")
            raise SystemExit(3)

        # Calculate date range
        oldest_date = min(p.published_date for p in pending_papers)
        newest_date = max(p.published_date for p in pending_papers)
        date_range = f"{oldest_date.strftime('%b %d')} - {newest_date.strftime('%b %d, %Y')}"

        # Send digest
        notifier.send_digest(summarized, len(pending_papers), date_range, config.interest_keywords)

        # Mark as processed
        included_ids = [rp.paper.arxiv_id for rp, _ in summarized]
        storage.mark_papers_processed(pending_papers, datetime.utcnow(), included_ids)

        # Clear pending
        storage.clear_pending_papers()

        storage.log_run("digest", len(summarized), "success")
        logger.info(f"✓ Digest completed: sent {len(summarized)} papers to {len(config.email_to)} recipient(s)")

        # Send success notification
        notifier.send_success_notification("digest", {
            "Papers Summarized": len(summarized),
            "Total Pending Processed": len(pending_papers),
            "Recipients": len(config.email_to),
            "Date Range": date_range,
            "Keywords Configured": len(config.interest_keywords) if config.interest_keywords else 0,
        })

        return 0

    except SystemExit as e:
        storage.log_run("digest", 0, "error", str(e))
        # Send error notification
        send_error_notification(
            notifier,
            "digest",
            e,
            {"pending_papers": len(pending_papers) if "pending_papers" in locals() else 0},
            config.data_dir,
        )
        raise

    except TimeoutError as e:
        logger.error(f"Operation timeout: {e}")
        storage.log_run("digest", 0, "error", "Timeout error")
        send_error_notification(notifier, "digest", e, {"error": "Operation timeout"}, config.data_dir)
        raise SystemExit(3)

    except Exception as e:
        logger.error(f"Unexpected error in digest mode: {e}", exc_info=True)
        storage.log_run("digest", 0, "error", str(e))
        send_error_notification(notifier, "digest", e, {}, config.data_dir)
        raise SystemExit(3)

    finally:
        storage.close()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="arXiv Digest Bot")
    parser.add_argument(
        "--mode", choices=["ingest", "digest"], required=True, help="Operation mode: ingest (daily) or digest (weekly)"
    )

    args = parser.parse_args()

    # Load configuration
    config = Config.from_env()

    # Setup logging
    setup_logging(config.data_dir)

    # Run appropriate mode
    if args.mode == "ingest":
        return ingest_mode(config)
    elif args.mode == "digest":
        return digest_mode(config)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit as e:
        sys.exit(e.code if hasattr(e, "code") else 1)
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
