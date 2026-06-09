"""
Email reporting functionality for the competitor monitoring tool.
"""
import html as html_lib
import logging
from datetime import datetime, UTC
from typing import List, Dict, Union
import resend
import markdown

from models import CompetitorChange

logger = logging.getLogger(__name__)

_EMAIL_STYLES = """
    <style>
        .analysis-content h2 {
            color: #1e40af;
            font-size: 1.25em;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
        }
        .analysis-content h3 {
            color: #1f2937;
            font-size: 1.1em;
            margin-top: 1em;
            margin-bottom: 0.5em;
        }
        .analysis-content ul, .analysis-content ol {
            margin: 0.5em 0;
            padding-left: 1.5em;
        }
        .analysis-content li {
            margin: 0.25em 0;
        }
        .analysis-content p {
            margin: 0.75em 0;
        }
        .analysis-content strong {
            color: #1f2937;
            font-weight: 600;
        }
    </style>
"""


class EmailReporter:
    """Sends HTML email digests via Resend."""

    def __init__(self, api_key: str, from_email: str, from_name: str, to_emails: List[str]):
        resend.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name
        self.to_emails = to_emails

    def _generate_changes_table(self, changes: List[CompetitorChange], change_analyses: Dict[str, str]) -> str:
        """Generate HTML table for detected changes with inline analysis."""
        changes_rows = "".join(
            f"""
                <tr>
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; vertical-align: top;">{html_lib.escape(change.company_name)}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; vertical-align: top;">
                        <a href="{html_lib.escape(change.url)}" target="_blank" rel="noopener noreferrer" style="color: #2563eb; text-decoration: none; font-weight: 500;">
                            {html_lib.escape(change.page_name)}
                        </a>
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #e5e7eb; vertical-align: top; color: #374151; font-size: 14px; line-height: 1.5;">
                        {html_lib.escape(change_analyses.get(change.name, "Analysis not available"))}
                    </td>
                </tr>
            """
            for change in changes
        )

        return f"""
        <table style="width: 100%; border-collapse: collapse; background-color: white; border: 1px solid #e5e7eb; margin: 15px 0;">
            <thead>
                <tr style="background-color: #f9fafb;">
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #1e40af; font-weight: 600; width: 15%;">Company</th>
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #1e40af; font-weight: 600; width: 20%;">Page</th>
                    <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e5e7eb; color: #1e40af; font-weight: 600; width: 65%;">Changes</th>
                </tr>
            </thead>
            <tbody>
                {changes_rows}
            </tbody>
        </table>
        """

    def _generate_html_digest(self, changes: List[CompetitorChange],
                              analysis: Union[str, Dict[str, str]], timestamp: str) -> str:
        """Generate HTML email digest."""
        styles = _EMAIL_STYLES

        # Handle both old (string) and new (dict) analysis formats
        if isinstance(analysis, dict):
            change_analyses = analysis
        else:
            # Legacy format - create empty dict, analysis will be shown separately
            change_analyses = {}

        # Generate content based on whether there are changes
        if changes:
            changes_section = f"""
                <h2 style="color: #1e40af; border-bottom: 2px solid #e5e7eb; padding-bottom: 10px; margin-bottom: 20px;">
                    Competitor Changes Detected: {len(changes)}
                </h2>

                {self._generate_changes_table(changes, change_analyses)}
            """
            header_color = "#2563eb"  # Blue for changes
        else:
            changes_section = f"""
                <div style="background-color: #f0fdf4; padding: 20px; border-radius: 8px; border-left: 4px solid #10b981; margin: 20px 0;">
                    <h2 style="color: #059669; margin: 0 0 10px 0;">✓ All Clear</h2>
                    <p style="margin: 0; color: #047857;">No competitor changes detected in this monitoring cycle. All tracked pages remain unchanged.</p>
                </div>
            """
            header_color = "#10b981"  # Green for no changes

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            {styles}
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px;">
            <div style="background-color: {header_color}; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
                <h1 style="margin: 0;">Competitor Intelligence Report</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">{timestamp}</p>
            </div>

            <div style="background-color: white; padding: 20px; border: 1px solid #e5e7eb; border-top: none;">
                {changes_section}

                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #e5e7eb; text-align: center; color: #6b7280; font-size: 14px;">
                    <p>Generated by Competitor Monitoring Tool</p>
                    <p>Powered by AI</p>
                </div>
            </div>
        </body>
        </html>
        """

        return html

    def send_digest(self, changes: List[CompetitorChange],
                    analysis: Union[str, Dict[str, str]], subject_prefix: str) -> bool:
        """Send email digest with changes and analysis."""
        now = datetime.now(UTC)
        timestamp = now.strftime("%B %d, %Y at %I:%M %p UTC")
        timestamp_short = now.strftime("%b %d, %Y")
        html_content = self._generate_html_digest(changes, analysis, timestamp)

        # Update subject based on whether there are changes
        if changes:
            subject = f"{subject_prefix} {len(changes)} change(s) detected - {timestamp_short}"
        else:
            subject = f"{subject_prefix} No changes detected - {timestamp_short}"

        try:
            for to_email in self.to_emails:
                params = {
                    "from": f"{self.from_name} <{self.from_email}>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html_content
                }

                resend.Emails.send(params)
                logger.info(f"Email sent successfully to {to_email}")

            return True
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False
