"""Email notification system for digests and errors."""

import logging
import smtplib
import socket
from dataclasses import dataclass
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Tuple

from src.ranker import RankedPaper

logger = logging.getLogger(__name__)


@dataclass
class ErrorDetails:
    """Error notification details."""

    mode: str
    timestamp: str
    error_type: str
    error_message: str
    exit_code: int
    context: dict
    logs: List[str]


class EmailNotifier:
    """Sends digest and error notification emails."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        email_from: str,
        digest_recipients: List[str],
        notification_recipient: str,
        digest_subject_prefix: str,
        notification_subject_prefix: str,
        notifications_enabled: bool,
    ):
        """
        Initialize email notifier.

        Args:
            smtp_host: SMTP server host
            smtp_port: SMTP server port
            smtp_username: SMTP username
            smtp_password: SMTP password
            email_from: From email address
            digest_recipients: List of digest recipients
            notification_recipient: Admin notification recipient (errors + success)
            digest_subject_prefix: Subject prefix for digest emails
            notification_subject_prefix: Subject prefix for notification emails
            notifications_enabled: Whether to send admin notifications
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.email_from = email_from
        self.digest_recipients = digest_recipients
        self.notification_recipient = notification_recipient
        self.digest_subject_prefix = digest_subject_prefix
        self.notification_subject_prefix = notification_subject_prefix
        self.notifications_enabled = notifications_enabled

        logger.info(
            f"Initialized email notifier (recipients={len(digest_recipients)}, "
            f"notifications={notifications_enabled})"
        )

    def send_digest(
        self,
        summarized_papers: List[Tuple[RankedPaper, str]],
        total_papers_fetched: int,
        date_range: str,
        interest_keywords: List[str] = None,
    ) -> None:
        """
        Send weekly digest email.

        Args:
            summarized_papers: List of (RankedPaper, summary) tuples
            total_papers_fetched: Total papers collected this week
            date_range: Date range string (e.g., "Jan 31 - Feb 7, 2026")
            interest_keywords: List of configured interest keywords (optional)

        Raises:
            SystemExit: If email sending fails after retries
        """
        display_count = len(summarized_papers)
        subject = f"{self.digest_subject_prefix} Top {display_count} of {total_papers_fetched} Papers - Week of {date_range}"

        html_body = self._render_digest_html(summarized_papers, total_papers_fetched, date_range, interest_keywords)

        logger.info(f"Sending digest to {len(self.digest_recipients)} recipient(s) via BCC")
        self._send_email(self.digest_recipients, subject, html_body, use_bcc=True)
        logger.info("Digest email sent successfully")

    def send_error_notification(self, error_details: ErrorDetails) -> None:
        """
        Send error notification email.

        Args:
            error_details: Error details to send
        """
        if not self.notifications_enabled:
            logger.info("Notifications disabled, skipping error notification")
            return

        subject = f"{self.notification_subject_prefix} ERROR - {error_details.mode.capitalize()} Failed - {datetime.now().strftime('%b %d, %Y')}"

        html_body = self._render_error_html(error_details)

        try:
            logger.info(f"Sending error notification to {self.notification_recipient}")
            self._send_email([self.notification_recipient], subject, html_body, max_retries=1)
            logger.info("Error notification sent")
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")
            # Don't raise - error notification failure shouldn't crash the job

    def send_success_notification(self, mode: str, stats: dict) -> None:
        """
        Send success summary notification email.

        Args:
            mode: Operation mode (ingest/digest)
            stats: Dictionary with run statistics
        """
        if not self.notifications_enabled:
            logger.info("Notifications disabled, skipping success notification")
            return

        subject = f"{self.notification_subject_prefix} SUCCESS - {mode.capitalize()} Completed - {datetime.now().strftime('%b %d, %Y')}"

        html_body = self._render_success_html(mode, stats)

        try:
            logger.info(f"Sending success notification to {self.notification_recipient}")
            self._send_email([self.notification_recipient], subject, html_body, max_retries=1)
            logger.info("Success notification sent")
        except Exception as e:
            logger.error(f"Failed to send success notification: {e}")
            # Don't raise - notification failure shouldn't crash the job

    def _send_email(self, recipients: List[str], subject: str, html_body: str, max_retries: int = 3, use_bcc: bool = False) -> None:
        """
        Send email with retry logic.

        Args:
            recipients: List of recipient email addresses
            subject: Email subject
            html_body: HTML email body
            max_retries: Maximum retry attempts
            use_bcc: If True, send via BCC (privacy-preserving for multiple recipients)

        Raises:
            SystemExit: If email sending fails after retries
        """
        msg = MIMEMultipart("alternative")
        msg["From"] = self.email_from

        if use_bcc:
            # For BCC: show sender in To field, hide actual recipients
            msg["To"] = self.email_from
            msg["Bcc"] = ", ".join(recipients)
        else:
            # For direct emails (notifications): show recipient in To field
            msg["To"] = ", ".join(recipients)

        msg["Subject"] = subject

        msg.attach(MIMEText(html_body, "html"))

        for attempt in range(max_retries):
            try:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30)
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
                server.quit()

                logger.info(f"Email sent successfully to {len(recipients)} recipient(s)")
                return

            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP authentication failed: {e}")
                raise SystemExit(4)  # Don't retry auth errors

            except smtplib.SMTPException as e:
                logger.warning(f"SMTP error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(10)

            except socket.timeout:
                logger.warning(f"SMTP timeout (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(15)

            except Exception as e:
                logger.error(f"Unexpected email error: {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(10)

        logger.error(f"Failed to send email after {max_retries} attempts")
        raise SystemExit(4)

    def _render_digest_html(
        self, summarized_papers: List[Tuple[RankedPaper, str]], total_papers: int, date_range: str, interest_keywords: List[str] = None
    ) -> str:
        """Render digest email as HTML."""
        # Count matched papers
        matched_count = sum(1 for rp, _ in summarized_papers if rp.matched_keywords)

        # Build paper cards
        paper_cards = []
        for ranked_paper, summary in summarized_papers:
            paper = ranked_paper.paper

            # Format categories
            categories_html = " ".join([f'<span class="category">{cat}</span>' for cat in paper.categories[:3]])

            # Format matched keywords
            matched_html = ""
            if ranked_paper.matched_keywords:
                keywords_str = ", ".join(ranked_paper.matched_keywords)
                matched_html = f'<div class="matched">🎯 Matches: {keywords_str}</div>'

            # Format date
            date_str = paper.published_date.strftime("%b %d, %Y")

            paper_card = f"""
            <div class="paper-card">
                <div class="paper-title">
                    <a href="{paper.arxiv_url}">{paper.title}</a>
                </div>
                <div class="paper-meta">
                    <a href="{paper.arxiv_url}">{paper.arxiv_id}</a> • {date_str}
                </div>
                <div class="paper-categories">{categories_html}</div>
                {matched_html}
                <div class="paper-summary">{summary}</div>
            </div>
            """
            paper_cards.append(paper_card)

        papers_html = "\n".join(paper_cards)

        # Build summary stats
        summary_html = f"<li>Showing top {len(summarized_papers)} of {total_papers} papers collected this week</li>"
        if interest_keywords:
            keywords_badges = " ".join([f'<span class="keyword-badge">{kw}</span>' for kw in interest_keywords])
            summary_html += f"<li>🔍 Filtering by keywords: {keywords_badges}</li>"
        if matched_count > 0:
            summary_html += f"<li>🎯 {matched_count} papers matched your keywords</li>"
        summary_html += f"<li>Collection period: {date_range}</li>"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }}
                .container {{ background-color: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                h1 {{ color: #2c3e50; margin-bottom: 20px; font-size: 24px; }}
                .summary {{ background-color: #f8f9fa; padding: 15px; border-radius: 6px; margin-bottom: 30px; }}
                .summary ul {{ margin: 10px 0; padding-left: 20px; }}
                .summary li {{ margin: 5px 0; }}
                .keyword-badge {{ display: inline-block; background-color: #fff3cd; color: #856404; padding: 3px 10px; border-radius: 12px; font-size: 13px; margin-right: 6px; margin-bottom: 4px; font-weight: 500; border: 1px solid #ffeeba; }}
                .paper-card {{ background-color: #fff; border: 1px solid #e1e4e8; border-radius: 6px; padding: 20px; margin-bottom: 20px; }}
                .paper-title {{ font-size: 18px; font-weight: 600; margin-bottom: 8px; }}
                .paper-title a {{ color: #0366d6; text-decoration: none; }}
                .paper-title a:hover {{ text-decoration: underline; }}
                .paper-meta {{ color: #586069; font-size: 14px; margin-bottom: 10px; }}
                .paper-meta a {{ color: #586069; text-decoration: none; }}
                .paper-categories {{ margin-bottom: 10px; }}
                .category {{ display: inline-block; background-color: #e1f5fe; color: #01579b; padding: 2px 8px; border-radius: 3px; font-size: 12px; margin-right: 5px; }}
                .matched {{ color: #2e7d32; font-size: 14px; margin-bottom: 10px; }}
                .paper-summary {{ color: #24292e; line-height: 1.6; }}
                .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #e1e4e8; color: #586069; font-size: 12px; text-align: center; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📊 arXiv Weekly Digest</h1>

                <div class="summary">
                    <strong>Week Summary</strong>
                    <ul>{summary_html}</ul>
                </div>

                {papers_html}

                <div class="footer">
                    Generated by arXiv Digest Bot • Powered by Claude AI
                </div>
            </div>
        </body>
        </html>
        """

    def _render_error_html(self, error: ErrorDetails) -> str:
        """Render error notification as HTML."""
        # Format logs
        logs_html = "<br>".join(error.logs[-50:]) if error.logs else "No logs available"

        # Format context
        context_items = [f"<li><strong>{k}:</strong> {v}</li>" for k, v in error.context.items()]
        context_html = "<ul>" + "".join(context_items) + "</ul>" if context_items else "No additional context"

        exit_code_msg = {
            1: "Configuration error",
            2: "arXiv API error",
            3: "Claude API error",
            4: "Email sending error",
            5: "No new papers",
        }.get(error.exit_code, "Unknown error")

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: monospace; background-color: #fff5f5; padding: 20px; }}
                .container {{ background-color: white; border: 2px solid #c62828; border-radius: 8px; padding: 30px; max-width: 700px; margin: 0 auto; }}
                h1 {{ color: #c62828; }}
                .error-box {{ background-color: #ffebee; border-left: 4px solid #c62828; padding: 15px; margin: 20px 0; }}
                .info-section {{ margin: 20px 0; }}
                .info-section h3 {{ color: #333; margin-bottom: 10px; }}
                .logs {{ background-color: #f5f5f5; padding: 15px; border-radius: 4px; font-size: 12px; overflow-x: auto; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>⚠️ arXiv Digest Bot Error Report</h1>

                <div class="error-box">
                    <strong>Error:</strong> {error.error_type}<br>
                    <strong>Message:</strong> {error.error_message}
                </div>

                <div class="info-section">
                    <h3>Details</h3>
                    <strong>Mode:</strong> {error.mode}<br>
                    <strong>Time:</strong> {error.timestamp}<br>
                    <strong>Exit Code:</strong> {error.exit_code} ({exit_code_msg})
                </div>

                <div class="info-section">
                    <h3>Context</h3>
                    {context_html}
                </div>

                <div class="info-section">
                    <h3>Recent Logs (last 50 lines)</h3>
                    <div class="logs">{logs_html}</div>
                </div>

                <div class="info-section">
                    <h3>Next Steps</h3>
                    <ul>
                        <li>Check the error message and context above</li>
                        <li>Review application logs for more details</li>
                        <li>Verify configuration and API keys</li>
                        <li>Next scheduled run will retry automatically</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """

    def _render_success_html(self, mode: str, stats: dict) -> str:
        """Render success notification as HTML."""
        # Format stats as list items
        stats_items = [f"<li><strong>{k}:</strong> {v}</li>" for k, v in stats.items()]
        stats_html = "<ul>" + "".join(stats_items) + "</ul>" if stats_items else "No additional details"

        # Mode-specific messaging
        if mode == "ingest":
            summary = "Successfully fetched and stored new papers from arXiv."
            icon = "📥"
        else:  # digest
            summary = "Successfully generated summaries and sent digest email."
            icon = "📧"

        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; padding: 20px; background-color: #f0f9ff; }}
                .container {{ background-color: white; border: 2px solid #0ea5e9; border-radius: 8px; padding: 30px; max-width: 700px; margin: 0 auto; }}
                h1 {{ color: #0369a1; margin-bottom: 10px; }}
                .success-box {{ background-color: #ecfdf5; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0; }}
                .info-section {{ margin: 20px 0; }}
                .info-section h3 {{ color: #333; margin-bottom: 10px; }}
                .timestamp {{ color: #6b7280; font-size: 14px; }}
                ul {{ margin: 10px 0; padding-left: 20px; }}
                li {{ margin: 5px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{icon} arXiv Digest Bot - Success Report</h1>
                <p class="timestamp">Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>

                <div class="success-box">
                    <strong>Mode:</strong> {mode.upper()}<br>
                    <strong>Status:</strong> ✅ SUCCESS<br>
                    <strong>Summary:</strong> {summary}
                </div>

                <div class="info-section">
                    <h3>Run Statistics</h3>
                    {stats_html}
                </div>

                <div class="info-section">
                    <p style="color: #6b7280; font-size: 14px;">
                        This is an automated notification from your arXiv Digest Bot.
                        The next scheduled run will execute according to your cron configuration.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
