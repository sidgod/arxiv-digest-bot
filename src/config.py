"""Configuration management for arXiv Digest Bot."""

import os
import re
import sys
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Config:
    """Application configuration loaded from environment variables."""

    # Claude API
    anthropic_api_key: str
    claude_model: str
    summary_max_tokens: int

    # arXiv Parameters
    arxiv_categories: List[str]
    arxiv_daily_fetch_limit: int
    arxiv_display_limit: int
    arxiv_search_query: Optional[str]

    # Interest Keywords
    interest_keywords: List[str]

    # Email Configuration
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    email_from: str
    email_to: List[str]  # Comma-separated, parsed to list
    email_subject_prefix: str

    # Notification Email Configuration (for both errors and success summaries)
    notification_email_to: str
    notification_email_prefix: str
    notifications_enabled: bool

    # Storage
    data_dir: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables with validation."""
        # Required fields
        anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        smtp_host = os.getenv("SMTP_HOST")
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        email_from = os.getenv("EMAIL_FROM")
        email_to = os.getenv("EMAIL_TO")

        # Check required fields
        required = {
            "ANTHROPIC_API_KEY": anthropic_api_key,
            "SMTP_HOST": smtp_host,
            "SMTP_USERNAME": smtp_username,
            "SMTP_PASSWORD": smtp_password,
            "EMAIL_FROM": email_from,
            "EMAIL_TO": email_to,
        }

        missing = [k for k, v in required.items() if not v]
        if missing:
            print(f"ERROR: Missing required configuration: {', '.join(missing)}")
            sys.exit(1)

        # Parse and validate email_to (comma-separated)
        email_to_list = [e.strip() for e in email_to.split(",") if e.strip()]
        if not email_to_list:
            print("ERROR: EMAIL_TO is empty after parsing")
            sys.exit(1)

        for email in email_to_list:
            if not cls._validate_email(email):
                print(f"ERROR: Invalid digest email: {email}")
                sys.exit(1)

        print(f"INFO: Digest will be sent to {len(email_to_list)} recipient(s)")

        # Parse categories
        categories_str = os.getenv("ARXIV_CATEGORIES", "cs.AI,cs.CL,cs.LG")
        categories = [c.strip() for c in categories_str.split(",") if c.strip()]

        # Parse interest keywords
        keywords_str = os.getenv("INTEREST_KEYWORDS", "")
        keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

        # Notification email configuration (backward compatible with ERROR_EMAIL_TO)
        notification_email_to = os.getenv("NOTIFICATION_EMAIL_TO") or os.getenv("ERROR_EMAIL_TO", "")
        if notification_email_to:
            if not cls._validate_email(notification_email_to):
                print(f"ERROR: Invalid notification email: {notification_email_to}")
                sys.exit(1)
        else:
            # Default to first EMAIL_TO recipient
            notification_email_to = email_to_list[0]
            print(f"INFO: NOTIFICATION_EMAIL_TO not set, using {notification_email_to} for notifications")

        notifications_enabled = os.getenv("NOTIFICATIONS_ENABLED") or os.getenv("ERROR_EMAIL_ENABLED", "true")
        notifications_enabled = notifications_enabled.lower() == "true"

        return cls(
            anthropic_api_key=anthropic_api_key,
            claude_model=os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929"),
            summary_max_tokens=int(os.getenv("SUMMARY_MAX_TOKENS", "150")),
            arxiv_categories=categories,
            arxiv_daily_fetch_limit=int(os.getenv("ARXIV_DAILY_FETCH_LIMIT", "15")),
            arxiv_display_limit=int(os.getenv("ARXIV_DISPLAY_LIMIT", "15")),
            arxiv_search_query=os.getenv("ARXIV_SEARCH_QUERY"),
            interest_keywords=keywords,
            smtp_host=smtp_host,
            smtp_port=int(os.getenv("SMTP_PORT", "587")),
            smtp_username=smtp_username,
            smtp_password=smtp_password,
            email_from=email_from,
            email_to=email_to_list,
            email_subject_prefix=os.getenv("EMAIL_SUBJECT_PREFIX", "[arXiv Digest]"),
            notification_email_to=notification_email_to,
            notification_email_prefix=os.getenv("NOTIFICATION_EMAIL_PREFIX", "[arXiv Bot]"),
            notifications_enabled=notifications_enabled,
            data_dir=os.getenv("DATA_DIR", "/app/data"),
        )

    @staticmethod
    def _validate_email(email: str) -> bool:
        """Basic email validation."""
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(pattern, email) is not None
