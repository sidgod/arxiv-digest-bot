"""Paper ranking by interest keywords."""

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple

from src.arxiv_scraper import Paper

logger = logging.getLogger(__name__)


@dataclass
class RankedPaper:
    """Paper with ranking score and matched keywords."""

    paper: Paper
    score: float
    matched_keywords: List[str]


class PaperRanker:
    """Ranks papers based on interest keywords."""

    def __init__(self, interest_keywords: Optional[List[str]] = None):
        """
        Initialize ranker.

        Args:
            interest_keywords: List of keywords to match (case-insensitive)
        """
        self.interest_keywords = interest_keywords or []
        self.has_keywords = len(self.interest_keywords) > 0

        if self.has_keywords:
            logger.info(f"Ranking enabled with {len(self.interest_keywords)} keywords: {', '.join(self.interest_keywords)}")
        else:
            logger.info("No interest keywords configured, will use chronological sorting")

    def rank_papers(self, papers: List[Paper]) -> List[RankedPaper]:
        """
        Rank papers by keyword relevance or date.

        Args:
            papers: List of Paper objects

        Returns:
            List of RankedPaper objects, sorted by score (descending)
            When keywords are configured, only returns papers that match at least one keyword
        """
        if not papers:
            return []

        ranked = []
        for paper in papers:
            score, matched = self._calculate_score(paper)
            ranked.append(RankedPaper(paper=paper, score=score, matched_keywords=matched))

        # If keywords configured, filter out papers with no matches (strict filtering)
        if self.has_keywords:
            original_count = len(ranked)
            ranked = [rp for rp in ranked if rp.matched_keywords]
            filtered_count = original_count - len(ranked)

            if filtered_count > 0:
                logger.info(f"Filtered out {filtered_count} papers with no keyword matches")

            if ranked:
                logger.info(f"Ranked {len(ranked)} papers matching keywords (filtered from {original_count} total)")
            else:
                logger.warning(f"No papers matched any keywords (filtered all {original_count} papers)")

        # Sort by score (descending) - higher score = more relevant
        ranked.sort(key=lambda x: x.score, reverse=True)

        if not self.has_keywords:
            logger.info(f"Sorted {len(papers)} papers chronologically")

        return ranked

    def _calculate_score(self, paper: Paper) -> Tuple[float, List[str]]:
        """
        Calculate relevance score for a paper.

        Args:
            paper: Paper to score

        Returns:
            Tuple of (score, matched_keywords)

        Scoring logic:
            - If keywords configured: title matches = 3pts, abstract matches = 1pt each (max 3)
            - If no keywords: use publication timestamp as score (newer = higher)
        """
        if not self.has_keywords:
            # Use timestamp as score (newer papers score higher)
            timestamp_score = paper.published_date.timestamp()
            return (timestamp_score, [])

        # Keyword-based scoring
        score = 0.0
        matched = []

        title_lower = paper.title.lower()
        abstract_lower = paper.abstract.lower()

        for keyword in self.interest_keywords:
            keyword_lower = keyword.lower()

            # Title matches (worth 3 points)
            if keyword_lower in title_lower:
                score += 3.0
                if keyword not in matched:
                    matched.append(keyword)

            # Abstract matches (worth 1 point each, max 3 total)
            elif keyword_lower in abstract_lower:
                score += 1.0
                if keyword not in matched:
                    matched.append(keyword)

        return (score, matched)
