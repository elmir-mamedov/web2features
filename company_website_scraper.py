import requests
from bs4 import BeautifulSoup
import re
from logger import setup_logger
from curl_cffi import requests as requests

logger = setup_logger()

def scrape_company_text(url: str, max_chars: int = 3000) -> str:
    try:
        response = requests.get(url, impersonate="chrome120", timeout=10)
        response.raise_for_status()
    except Exception:
        # fallback — try without SSL verification for sites with bad certificates
        try:
            response = requests.get(url, impersonate="chrome120", timeout=10, verify=False)
            response.raise_for_status()
            logger.warning(f"SSL verification disabled for {url}")
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {e}")
            return ""
    soup = BeautifulSoup(response.text, "html.parser")

    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    result = text[:max_chars]

    logger.debug(f"Scraped {len(result)} chars from {url}")
    return result

def scrape_multiple_urls(urls: list[str], max_chars_per_page: int = 2000) -> str:
    """
    Scrape multiple URLs and concatenate the text.
    Each page is labeled so the LLM knows where content comes from.
    """
    all_text = []

    for url in urls:
        text = scrape_company_text(url, max_chars=max_chars_per_page)
        if text:
            all_text.append(f"--- PAGE: {url} ---\n{text}")
            logger.info(f"Scraped {len(text)} chars from {url}")
            logger.debug(f"Content from {url}:\n{text[:2000]}")
        else:
            logger.warning(f"Nothing scraped from {url}")

    return "\n\n".join(all_text)

if __name__ == "__main__":
    from sitemap_scraper import get_relevant_urls

    for test_url in ["https://www.albert.cz/"]:
        print(f"\n{'='*60}")
        print(f"TESTING: {test_url}")
        print('='*60)

        urls = get_relevant_urls(test_url)
        text = scrape_multiple_urls(urls)
        print(f"\n{'=' * 60}")
        print(f"TOTAL CHARS SCRAPED: {len(text)}")
        print('=' * 60)
