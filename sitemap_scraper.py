import requests
import json
import re
from bs4 import BeautifulSoup
from logger import setup_logger
from llm_client import chat

logger = setup_logger()


def prefilter_urls(urls: list[str], base_url: str) -> list[str]:
    """
    Remove noise URLs before sending to LLM.
    Keep only URLs with 1-2 path segments, exclude known noise patterns.
    """
    NOISE_PATTERNS = {
        "blog", "demo", "dekujeme", "registrace", "cookies", "whistleblowing",
        "oznameni", "zpetna-vazba", "test-ebook", "integrace", "meet-up",
        "standardni-exporty", "google-pay", "apple-pay", "mastercard"
    }

    filtered = []
    base = base_url.rstrip("/")

    for url in urls:
        path = url.replace(base, "").strip("/")

        # skip homepage itself
        if not path:
            continue

        segments = path.split("/")

        # keep only 1-2 segment paths
        if len(segments) > 2:
            continue

        # skip if any segment matches noise patterns
        if any(noise in segments for noise in NOISE_PATTERNS):
            continue

        filtered.append(url)

    logger.info(f"Prefiltered {len(urls)} → {len(filtered)} URLs")
    return filtered

def get_sitemap_urls(sitemap_url: str) -> list[str]:
    try:
        r = requests.get(sitemap_url, timeout=10)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch sitemap {sitemap_url}: {e}")
        return []

    # handle gzip compressed sitemaps
    content = r.content
    if sitemap_url.endswith(".gz"):
        import gzip
        try:
            content = gzip.decompress(content)
        except Exception as e:
            logger.error(f"Failed to decompress gzip sitemap {sitemap_url}: {e}")
            return []

    soup = BeautifulSoup(content, "xml")

    # sitemap index — recurse into sub-sitemaps
    sub_sitemaps = soup.find_all("sitemap")
    if sub_sitemaps:
        urls = []
        for sitemap in sub_sitemaps:
            loc = sitemap.find("loc")
            if loc:
                urls.extend(get_sitemap_urls(loc.text.strip()))
        return urls

    return [loc.text.strip() for loc in soup.find_all("loc")]


def select_relevant_urls(urls: list[str], base_url: str) -> list[str]:
    """
    Send full URL list to LLM and ask it to select 3 most relevant
    pages for understanding company identity, product, and structure.
    Main page is always included separately — LLM selects additional pages only.
    """
    urls = prefilter_urls(urls, base_url)
    url_list = "\n".join(urls)

    prompt = f"""You are analyzing a company website. The base URL is: {base_url}

Below is a list of all pages found in the sitemap.
Select up to 3 additional pages (NOT the homepage) that would be most useful for 
understanding:
- what the company does
- who they are
- what products or services they offer
- their structure or team

Return ONLY a valid JSON array of URLs. No explanation, no markdown, no code blocks.
Example: ["https://example.com/about", "https://example.com/products"]

If no pages are clearly relevant, return an empty array: []

URLs:
{url_list}
"""

    try:
        raw = chat(
            prompt=prompt,
            system="You are a web analyst. Return ONLY a valid JSON array of URLs, nothing else."
        )
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        selected = json.loads(raw)

        # validate — only keep URLs that were actually in the sitemap
        valid = [u for u in selected if u in urls]
        logger.info(f"LLM selected {len(valid)} additional pages: {valid}")
        return valid[:3]

    except Exception as e:
        logger.error(f"LLM URL selection failed: {e}")
        return []

def find_sitemap_url(base_url: str) -> str | None:
    """
    Find sitemap URL for a given base URL.
    First tries /sitemap.xml, then falls back to robots.txt.
    Returns sitemap URL or None if not found.
    """
    base = base_url.rstrip("/")

    # try standard location first
    standard = f"{base}/sitemap.xml"
    try:
        r = requests.get(standard, timeout=10)
        if r.status_code == 200:
            return standard
    except Exception:
        pass

    # fall back to robots.txt
    try:
        r = requests.get(f"{base}/robots.txt", timeout=10)
        r.raise_for_status()
        for line in r.text.splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()
                logger.info(f"Found sitemap via robots.txt: {sitemap_url}")
                return sitemap_url
    except Exception as e:
        logger.warning(f"robots.txt not found for {base_url}: {e}")

    return None

def get_relevant_urls(base_url: str) -> list[str]:
    base = base_url.rstrip("/")

    sitemap_url = find_sitemap_url(base_url)
    if not sitemap_url:
        logger.warning(f"No sitemap found for {base_url} — scraping homepage only")
        return [base_url]

    logger.info(f"Fetching sitemap from {sitemap_url}")
    urls = get_sitemap_urls(sitemap_url)

    if not urls:
        logger.warning(f"No URLs found in sitemap — scraping homepage only")
        return [base_url]

    logger.info(f"Found {len(urls)} URLs in sitemap")
    additional = select_relevant_urls(urls, base_url)
    return [base_url] + additional

if __name__ == "__main__":
    for test_url in ["https://www.albert.cz", "https://en.atg.cz"]:
        print(f"\n--- {test_url} ---")
        urls = get_relevant_urls(test_url)