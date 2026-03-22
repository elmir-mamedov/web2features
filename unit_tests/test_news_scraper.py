import pytest
from news_scraper import extract_domain_from_url


@pytest.mark.parametrize("url, expected", [
    ("https://www.fidoo.com",       "fidoo"),
    ("https://www.albert.cz/",      "albert"),
    ("https://en.atg.cz/",          "atg"),
    ("https://cs.example.com/about","example"),
    ("http://company.co.uk/",       "company"),
    ("https://www2.somebank.cz/",   "somebank"),
    ("https://de.company.eu",       "company"),
])
def test_extract_domain_from_url(url, expected):
    assert extract_domain_from_url(url) == expected