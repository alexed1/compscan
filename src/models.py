"""
Domain models for the competitor monitoring tool.
"""
from dataclasses import dataclass, field


@dataclass
class CompetitorChange:
    """Represents a detected change in a competitor website."""

    name: str
    url: str
    content: str
    last_checked: str
    company_name: str = field(init=False)
    page_name: str = field(init=False)

    def __post_init__(self):
        """Extract company and page names from full name."""
        if ' - ' in self.name:
            parts = self.name.split(' - ', 1)
            self.company_name = parts[0]
            self.page_name = parts[1]
        else:
            self.company_name = self.name
            self.page_name = 'Homepage'

    def to_dict(self):
        """Convert to dictionary for backwards compatibility."""
        return {
            'name': self.name,
            'url': self.url,
            'content': self.content,
            'last_checked': self.last_checked,
            'company_name': self.company_name,
            'page_name': self.page_name
        }
