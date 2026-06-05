"""
Blog content extraction service for monitoring blog pages.
Focuses on extracting actual blog posts while ignoring promotional content.
"""
import logging
from typing import Optional, List
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class BlogExtractor:
    """Extracts blog post content from blog/resource pages."""

    # Common promotional/CTA phrases to ignore
    PROMOTIONAL_PATTERNS = [
        r'sign up',
        r'subscribe',
        r'stay in the know',
        r'one email',
        r'get the latest',
        r'join our newsletter',
        r'stay current',
        r'stay up[- ]to[- ]date',
        r'email address',
        r'thank you.*submission',
        r'oops.*wrong',
        r'view all',
        r'show more',
        r'show less',
        r'load more',
        r'see all',
        r'upcoming webinars?',
        r'recent webinars?',
        r'editor.*picks?',
        r'featured',
        r'popular posts?',
        r'related posts?',
        r'you may also like',
    ]

    # Patterns that indicate actual blog content
    BLOG_INDICATORS = [
        r'\d{4}',  # Years like 2025, 2026
        r'read more',
        r'learn more',
        r'case study',
        r'guide',
        r'report',
        r'article',
        r'webinar',
        r'post',
        r'published',
    ]

    def __init__(self):
        self.promo_regex = re.compile('|'.join(self.PROMOTIONAL_PATTERNS), re.IGNORECASE)
        self.blog_regex = re.compile('|'.join(self.BLOG_INDICATORS), re.IGNORECASE)

    def extract_blog_posts(self, html: str) -> str:
        """
        Extract only blog post content from HTML.

        Returns a string with blog post titles and metadata, excluding promotional content.
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Remove all scripts, styles, and non-content elements
        for tag in soup(['script', 'style', 'noscript', 'meta', 'link', 'head']):
            tag.decompose()

        # Remove navigation, headers, footers
        for tag in soup.find_all(['nav', 'header', 'footer']):
            tag.decompose()

        # Remove common promotional containers by class/id
        for tag in soup.find_all(attrs={"class": lambda x: x and any(
            keyword in str(x).lower() for keyword in [
                "nav", "header", "footer", "menu", "sidebar",
                "newsletter", "subscribe", "signup", "cta", "banner"
            ]
        )}):
            tag.decompose()

        for tag in soup.find_all(attrs={"id": lambda x: x and any(
            keyword in str(x).lower() for keyword in [
                "nav", "header", "footer", "menu", "sidebar",
                "newsletter", "subscribe", "signup"
            ]
        )}):
            tag.decompose()

        # Extract text
        text = soup.get_text(separator='\n', strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        # Filter to blog-relevant content
        blog_lines = self._filter_blog_content(lines)

        return '\n'.join(blog_lines)

    def _filter_blog_content(self, lines: List[str]) -> List[str]:
        """
        Filter lines to keep only blog post content.

        Strategy:
        1. Remove lines that match promotional patterns
        2. Keep lines that appear to be blog titles or metadata
        3. Remove very short lines (likely navigation)
        4. Remove standalone category/tag words
        """
        filtered = []

        for line in lines:
            # Skip empty or very short lines
            if len(line) <= 3:
                continue

            # Skip copyright notices
            if any(pattern in line.lower() for pattern in ['© 20', 'all rights reserved', 'cookie preferences', 'privacy']):
                continue

            # Skip promotional content
            if self.promo_regex.search(line):
                logger.debug(f"Skipping promotional line: {line[:50]}")
                continue

            # Skip single-word lines (likely navigation/categories)
            # BUT keep if it has blog indicators
            words = line.split()
            if len(words) == 1:
                if len(line) < 20 and not self.blog_regex.search(line):
                    continue

            # Skip lines that are just repeated category tags
            if len(words) <= 2 and line.lower() in ['sales tax', 'tax update', 'finance', 'tech',
                                                       'leadership', 'billing', 'accounting', 'all',
                                                       'case study', 'guide', 'article', 'webinar',
                                                       'tool', 'template', 'report', 'news']:
                continue

            # Keep lines that look like real content
            # - Have multiple words (likely titles or descriptions)
            # - Or have blog indicators like years, "read more", etc.
            if len(words) >= 3 or self.blog_regex.search(line):
                filtered.append(line)

        return filtered

    def extract_blog_titles(self, html: str) -> List[str]:
        """
        Extract just the blog post titles from HTML.

        Returns a list of blog post titles.
        """
        content = self.extract_blog_posts(html)
        lines = content.split('\n')

        titles = []
        for i, line in enumerate(lines):
            # Heuristic: titles are usually longer than 10 chars
            # and followed by descriptions or "Read more"
            if len(line) > 10:
                # Check if next line suggests this is a title
                if i + 1 < len(lines):
                    next_line = lines[i + 1].lower()
                    if 'read more' in next_line or 'learn more' in next_line:
                        titles.append(line)
                        continue

                # Or if the line looks like a title (ends with question mark, or has colon)
                if line.endswith('?') or ':' in line:
                    titles.append(line)
                    continue

                # Or if it's a longer descriptive line (likely a title)
                if len(line) > 40 and len(line.split()) >= 5:
                    titles.append(line)

        return titles

    def is_blog_page(self, url: str) -> bool:
        """
        Determine if a URL is likely a blog/resource page.

        Blog pages typically have URLs containing: blog, news, resources, articles, insights
        """
        blog_keywords = ['blog', 'news', 'resource', 'article', 'insight', 'latest', 'updates']
        url_lower = url.lower()
        return any(keyword in url_lower for keyword in blog_keywords)
