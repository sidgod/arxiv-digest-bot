"""SQLite storage for tracking papers and runs."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.arxiv_scraper import Paper

logger = logging.getLogger(__name__)


class Storage:
    """Manages SQLite database for paper tracking."""

    def __init__(self, db_path: str):
        """
        Initialize storage.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

        # Ensure parent directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Access columns by name
        self._initialize_schema()

        logger.info(f"Initialized storage at {db_path}")

    def _initialize_schema(self):
        """Create database tables if they don't exist."""
        cursor = self.conn.cursor()

        # Pending papers (staging area)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS pending_papers (
                arxiv_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                abstract TEXT NOT NULL,
                categories TEXT NOT NULL,
                published_date TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                arxiv_url TEXT NOT NULL
            )
            """
        )

        # Processed papers (history)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS processed_papers (
                arxiv_id TEXT PRIMARY KEY,
                title TEXT,
                processed_at TEXT NOT NULL,
                digest_date TEXT NOT NULL,
                included_in_digest INTEGER NOT NULL
            )
            """
        )

        # Run logs
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                papers_count INTEGER,
                status TEXT NOT NULL,
                error_message TEXT
            )
            """
        )

        self.conn.commit()
        logger.debug("Database schema initialized")

    def add_pending_papers(self, papers: List[Paper]) -> int:
        """
        Add papers to pending queue.

        Args:
            papers: List of Paper objects

        Returns:
            Number of papers added (excluding duplicates)
        """
        if not papers:
            return 0

        added = 0
        cursor = self.conn.cursor()

        try:
            for paper in papers:
                try:
                    cursor.execute(
                        """
                        INSERT OR IGNORE INTO pending_papers
                        (arxiv_id, title, abstract, categories, published_date, fetched_at, arxiv_url)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            paper.arxiv_id,
                            paper.title,
                            paper.abstract,
                            ",".join(paper.categories),
                            paper.published_date.isoformat(),
                            datetime.utcnow().isoformat(),
                            paper.arxiv_url,
                        ),
                    )
                    if cursor.rowcount > 0:
                        added += 1
                except sqlite3.IntegrityError:
                    logger.debug(f"Paper {paper.arxiv_id} already exists, skipping")

            self.conn.commit()
            logger.info(f"Added {added} new papers to pending queue (skipped {len(papers) - added} duplicates)")
            return added

        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                logger.error("Database locked - another process may be running")
            else:
                logger.error(f"Database error: {e}")
            raise SystemExit(1)

        except Exception as e:
            logger.error(f"Unexpected database error: {e}")
            self.conn.rollback()
            raise SystemExit(1)

    def get_all_pending_papers(self) -> List[Paper]:
        """
        Retrieve all pending papers.

        Returns:
            List of Paper objects
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM pending_papers ORDER BY published_date DESC")

        papers = []
        for row in cursor.fetchall():
            paper = Paper(
                arxiv_id=row["arxiv_id"],
                title=row["title"],
                abstract=row["abstract"],
                categories=row["categories"].split(","),
                published_date=datetime.fromisoformat(row["published_date"]),
                arxiv_url=row["arxiv_url"],
            )
            papers.append(paper)

        logger.info(f"Retrieved {len(papers)} pending papers")
        return papers

    def is_paper_pending_or_processed(self, arxiv_id: str) -> bool:
        """Check if paper is already in pending or processed tables."""
        cursor = self.conn.cursor()

        cursor.execute("SELECT 1 FROM pending_papers WHERE arxiv_id = ?", (arxiv_id,))
        if cursor.fetchone():
            return True

        cursor.execute("SELECT 1 FROM processed_papers WHERE arxiv_id = ?", (arxiv_id,))
        if cursor.fetchone():
            return True

        return False

    def mark_papers_processed(
        self, all_papers: List[Paper], digest_date: datetime, included_ids: List[str]
    ) -> None:
        """
        Mark papers as processed after sending digest.

        Args:
            all_papers: All papers that were pending
            digest_date: Timestamp of the digest
            included_ids: arXiv IDs of papers included in digest
        """
        cursor = self.conn.cursor()
        processed_at = datetime.utcnow().isoformat()
        digest_date_str = digest_date.isoformat()

        try:
            for paper in all_papers:
                included = 1 if paper.arxiv_id in included_ids else 0
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO processed_papers
                    (arxiv_id, title, processed_at, digest_date, included_in_digest)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (paper.arxiv_id, paper.title, processed_at, digest_date_str, included),
                )

            self.conn.commit()
            logger.info(f"Marked {len(all_papers)} papers as processed ({len(included_ids)} included in digest)")

        except Exception as e:
            logger.error(f"Error marking papers as processed: {e}")
            self.conn.rollback()
            raise

    def clear_pending_papers(self) -> None:
        """Clear all pending papers."""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM pending_papers")
        self.conn.commit()
        logger.info("Cleared pending papers table")

    def get_last_successful_ingest_time(self) -> Optional[datetime]:
        """
        Get timestamp of last successful ingest run.

        Returns:
            Datetime of last successful ingest, or None if no successful ingests
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            SELECT timestamp FROM runs
            WHERE run_type = 'ingest' AND status = 'success'
            ORDER BY timestamp DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()
        if row:
            timestamp = datetime.fromisoformat(row["timestamp"])
            logger.debug(f"Last successful ingest: {timestamp}")
            return timestamp

        logger.debug("No previous successful ingest found")
        return None

    def log_run(
        self, run_type: str, papers_count: int, status: str, error_message: Optional[str] = None
    ) -> None:
        """
        Log a run (ingest or digest).

        Args:
            run_type: 'ingest' or 'digest'
            papers_count: Number of papers processed
            status: 'success', 'error', or 'no_papers'
            error_message: Optional error message
        """
        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO runs (run_type, timestamp, papers_count, status, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_type, datetime.utcnow().isoformat(), papers_count, status, error_message),
        )
        self.conn.commit()
        logger.debug(f"Logged {run_type} run: status={status}, papers={papers_count}")

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.debug("Database connection closed")
