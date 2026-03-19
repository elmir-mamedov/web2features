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


if __name__ == "__main__":
    url = "https://www.fidoo.com"
    text = scrape_company_text(url)
    print(f"Scraped {len(text)} characters\n")
    print(text[:500])