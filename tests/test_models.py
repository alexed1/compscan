"""
Tests for CompetitorChange model
"""
import pytest
from src.models import CompetitorChange


def test_name_splits_on_dash(self=None):
    c = CompetitorChange(name="Acme Corp - Homepage", url="https://acme.com",
                         content="", last_checked="now")
    assert c.company_name == "Acme Corp"
    assert c.page_name == "Homepage"


def test_name_without_dash_defaults_page_name():
    c = CompetitorChange(name="Acme Corp", url="https://acme.com",
                         content="", last_checked="now")
    assert c.company_name == "Acme Corp"
    assert c.page_name == "Homepage"


def test_name_with_multiple_dashes_splits_on_first():
    c = CompetitorChange(name="Acme Corp - Blog - Q2", url="https://acme.com",
                         content="", last_checked="now")
    assert c.company_name == "Acme Corp"
    assert c.page_name == "Blog - Q2"


def test_to_dict_contains_all_keys():
    c = CompetitorChange(name="Foo - Bar", url="https://foo.com",
                         content="stuff", last_checked="yesterday")
    d = c.to_dict()
    assert set(d.keys()) == {"name", "url", "content", "last_checked", "company_name", "page_name"}


def test_to_dict_values_match_attributes():
    c = CompetitorChange(name="Foo - Bar", url="https://foo.com",
                         content="stuff", last_checked="yesterday")
    d = c.to_dict()
    assert d["name"] == "Foo - Bar"
    assert d["url"] == "https://foo.com"
    assert d["content"] == "stuff"
    assert d["last_checked"] == "yesterday"
    assert d["company_name"] == "Foo"
    assert d["page_name"] == "Bar"


def test_name_with_only_dash():
    c = CompetitorChange(name=" - ", url="https://x.com", content="", last_checked="")
    assert c.company_name == ""
    assert c.page_name == ""
