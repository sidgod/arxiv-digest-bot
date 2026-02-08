"""Claude API integration for paper summarization."""

import logging
import time
from typing import List, Tuple

import anthropic

from src.ranker import RankedPaper

logger = logging.getLogger(__name__)


class ClaudeSummarizer:
    """Generates paper summaries using Claude API."""

    def __init__(self, api_key: str, model: str, max_tokens: int):
        """
        Initialize summarizer.

        Args:
            api_key: Anthropic API key
            model: Claude model name
            max_tokens: Maximum tokens per summary
        """
        self.client = anthropic.Anthropic(
            api_key=api_key,
            timeout=60.0,  # 60 second timeout for API calls
        )
        self.model = model
        self.max_tokens = max_tokens

        logger.info(f"Initialized Claude summarizer (model={model}, max_tokens={max_tokens}, timeout=60s)")

    def batch_summarize(self, ranked_papers: List[RankedPaper]) -> List[Tuple[RankedPaper, str]]:
        """
        Summarize multiple papers with partial failure tolerance.

        Args:
            ranked_papers: List of RankedPaper objects

        Returns:
            List of tuples (RankedPaper, summary)

        Raises:
            SystemExit: If more than 50% of summaries fail
        """
        if not ranked_papers:
            return []

        logger.info(f"Starting batch summarization of {len(ranked_papers)} papers")
        results = []
        failed_count = 0

        for i, ranked_paper in enumerate(ranked_papers, 1):
            try:
                summary = self.summarize_paper(ranked_paper.paper.title, ranked_paper.paper.abstract)
                results.append((ranked_paper, summary))
                logger.info(f"Summarized paper {i}/{len(ranked_papers)}: {ranked_paper.paper.arxiv_id}")
            except Exception as e:
                logger.error(f"Failed to summarize {ranked_paper.paper.arxiv_id}: {e}")
                failed_count += 1
                # Add with fallback summary
                results.append((ranked_paper, "[Summary unavailable]"))

        # Check failure threshold
        failure_rate = failed_count / len(ranked_papers)
        if failure_rate > 0.5:
            logger.error(f"Too many summarization failures: {failed_count}/{len(ranked_papers)} ({failure_rate:.1%})")
            raise SystemExit(3)

        if failed_count > 0:
            logger.warning(f"Completed with {failed_count} failures ({failure_rate:.1%})")
        else:
            logger.info("All summaries completed successfully")

        return results

    def summarize_paper(self, title: str, abstract: str, max_retries: int = 3) -> str:
        """
        Generate summary for a single paper with retry logic.

        Args:
            title: Paper title
            abstract: Paper abstract
            max_retries: Maximum retry attempts

        Returns:
            Generated summary text

        Raises:
            Exception: If all retries fail
        """
        prompt = self._build_prompt(title, abstract)

        for attempt in range(max_retries):
            try:
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                )

                summary = message.content[0].text.strip()
                return summary

            except anthropic.RateLimitError as e:
                wait = 60 * (attempt + 1)
                logger.warning(f"Claude rate limit hit, waiting {wait}s (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)

            except anthropic.APIError as e:
                logger.warning(f"Claude API error: {e}, retry {attempt + 1}/{max_retries}")
                time.sleep(5)

            except Exception as e:
                logger.error(f"Unexpected error in Claude API: {e}")
                if attempt == max_retries - 1:
                    raise

        raise Exception("Failed to generate summary after all retries")

    @staticmethod
    def _build_prompt(title: str, abstract: str) -> str:
        """Build summarization prompt for Claude."""
        return f"""You are summarizing an academic paper for busy AI/ML practitioners and technical architects.

Paper title: {title}

Abstract: {abstract}

Provide a 2-3 sentence summary that:
1. Explains the main contribution or finding
2. Highlights novel techniques or approaches
3. Notes practical applications or implications for engineers

Keep it concise, accessible, and focused on what makes this paper relevant."""
