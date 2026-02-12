"""arXiv API scraper for fetching research papers."""

import logging
import socket
import time
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

import arxiv
import requests

logger = logging.getLogger(__name__)

# Set global socket timeout for arXiv API calls (60 seconds)
socket.setdefaulttimeout(60.0)


@dataclass
class Paper:
    """Research paper metadata."""

    arxiv_id: str
    title: str
    abstract: str
    categories: List[str]
    published_date: datetime
    arxiv_url: str


class ArxivScraper:
    """Scrapes papers from arXiv API."""

    def __init__(self, categories: List[str], search_query: Optional[str] = None):
        """
        Initialize scraper.

        Args:
            categories: arXiv categories to search (e.g., ['cs.AI', 'cs.LG'])
            search_query: Optional additional search query
        """
        self.categories = categories
        self.search_query = search_query
        # Configure client with reasonable timeouts
        self.client = arxiv.Client(
            page_size=50,  # Balanced: fast enough to avoid timeouts, still efficient
            delay_seconds=3,  # Respect rate limits
            num_retries=3,  # Built-in retries
        )

    def fetch_papers(self, max_results: int, since_date: Optional[datetime] = None, max_retries: int = 3) -> List[Paper]:
        """
        Fetch papers from arXiv with retry logic.

        Args:
            max_results: Maximum number of papers to fetch
            since_date: Only fetch papers published after this date
            max_retries: Maximum number of retry attempts

        Returns:
            List of Paper objects

        Raises:
            SystemExit: If fetching fails after retries
        """
        query = self._build_query(since_date)

        if since_date:
            logger.info(f"Fetching up to {max_results} papers published after {since_date.strftime('%Y-%m-%d %H:%M')} with query: {query}")
        else:
            logger.info(f"Fetching up to {max_results} papers with query: {query}")

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    logger.warning(f"Retry attempt {attempt + 1}/{max_retries} for arXiv API")

                search = arxiv.Search(
                    query=query,
                    max_results=max_results,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending,
                )

                papers = []
                for result in self.client.results(search):
                    # Filter by date if since_date is provided
                    if since_date:
                        # Normalize both dates to naive UTC for comparison
                        # arXiv API returns timezone-aware datetimes, but since_date from DB is naive
                        result_date = result.published.replace(tzinfo=None) if result.published.tzinfo else result.published
                        compare_date = since_date.replace(tzinfo=None) if since_date.tzinfo else since_date

                        if result_date <= compare_date:
                            # arXiv returns papers in descending date order
                            # Once we hit a paper older than since_date, we can stop
                            logger.info(f"Reached papers older than {since_date.strftime('%Y-%m-%d %H:%M')}, stopping")
                            break

                    # Normalize published_date to timezone-naive UTC
                    # This ensures consistency with dates loaded from database
                    published_date = result.published.replace(tzinfo=None) if result.published.tzinfo else result.published

                    paper = Paper(
                        arxiv_id=result.entry_id.split("/")[-1],  # Extract ID from URL
                        title=result.title.strip(),
                        abstract=result.summary.strip(),
                        categories=result.categories,
                        published_date=published_date,
                        arxiv_url=result.entry_id,
                    )
                    papers.append(paper)

                    # Stop if we've collected enough papers
                    if len(papers) >= max_results:
                        break

                attempts_msg = f" (after {attempt + 1} attempt{'s' if attempt > 0 else ''})" if attempt > 0 else ""
                logger.info(f"Successfully fetched {len(papers)} papers{attempts_msg}")
                return papers

            except arxiv.HTTPError as e:
                if e.status == 429:  # Rate limit
                    wait = 2 ** attempt
                    logger.warning(f"Rate limited by arXiv, waiting {wait}s (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait)
                elif e.status >= 500:  # Server error
                    logger.warning(f"arXiv server error {e.status}, retrying (attempt {attempt + 1}/{max_retries})")
                    time.sleep(5)
                else:
                    logger.error(f"arXiv API error {e.status}: {e}")
                    raise SystemExit(2)

            except requests.ConnectionError as e:
                logger.warning(f"Network error: {e}, retrying (attempt {attempt + 1}/{max_retries})")
                time.sleep(10)

            except Exception as e:
                logger.error(f"Unexpected error fetching papers: {e}")
                raise SystemExit(2)

        logger.error(f"Failed to fetch papers after {max_retries} attempts")
        raise SystemExit(2)

    def _build_query(self, since_date: Optional[datetime] = None) -> str:
        """Build arXiv search query from categories, optional search terms, and date filter."""
        # Build category query (OR logic)
        category_query = " OR ".join([f"cat:{cat}" for cat in self.categories])

        query_parts = [f"({category_query})"]

        # Add search query if provided
        if self.search_query:
            query_parts.append(f"({self.search_query})")

        # Add date filter if provided
        # arXiv API doesn't support date filtering in query, so we'll filter results after fetching
        # The API always returns newest first, so we fetch more and filter client-side

        return " AND ".join(query_parts)
