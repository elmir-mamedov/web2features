from curl_cffi import requests as cffi_requests
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
        "standardni-exporty", "google-pay", "apple-pay", "mastercard",
        "my-account", "muj-ucet", "order", "search", "secure", "account"
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

def get_sitemap_urls(sitemap_url: str, base_url: str = "") -> list[str]:
    try:
        r = cffi_requests.get(sitemap_url, timeout=10, impersonate="chrome120")
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

def extract_links_from_homepage(base_url: str) -> list[str]:
    """
    Scrape homepage and extract all internal links as fallback
    when sitemap doesn't contain identity pages.
    """
    try:
        r = cffi_requests.get(base_url, impersonate="chrome120", timeout=10)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to fetch homepage {base_url}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    base = base_url.rstrip("/")
    links = set()

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # only internal links
        if href.startswith("/"):
            full_url = base + href.split("?")[0].split("#")[0]
            links.add(full_url)
        elif href.startswith(base):
            links.add(href.split("?")[0].split("#")[0])

    # keep only 1-2 segment paths
    filtered = [
        u for u in links
        if 1 <= len(u.replace(base, "").strip("/").split("/")) <= 2
    ]

    for link in sorted(filtered):
        logger.debug(f"  homepage link: {link}")
    logger.info(f"Extracted {len(filtered)} internal links from homepage")
    return filtered

def select_relevant_urls(urls: list[str], base_url: str) -> list[str]:
    """
    Send full URL list to LLM and ask it to select 3 most relevant
    pages for understanding company identity, product, and structure.
    Main page is always included separately — LLM selects additional pages only.
    """
    urls = prefilter_urls(urls, base_url)

    # if still too many after prefilter, fall back to homepage links only
    if len(urls) > 200:
        logger.warning(f"Too many URLs after prefilter ({len(urls)}) — falling back to homepage links only")
        urls = extract_links_from_homepage(base_url)
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
        r = cffi_requests.get(standard, timeout=10, impersonate="chrome120")
        if r.status_code == 200:
            logger.info(f"Found sitemap: {standard}")
            return standard
    except Exception:
        pass

    # fall back to robots.txt
    try:
        r = cffi_requests.get(f"{base}/robots.txt", impersonate="chrome120", timeout=10)
        r.raise_for_status()
        sitemap_urls = []
        for line in r.text.splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_urls.append(line.split(":", 1)[1].strip())
        if sitemap_urls:
            return select_relevant_sitemap(sitemap_urls, base_url)
    except Exception as e:
        logger.warning(f"robots.txt not found for {base_url}: {e}")

    return None

def select_relevant_sitemap(sitemap_urls: list[str], base_url: str) -> str | None:
    """
    When robots.txt exposes multiple sitemaps, ask LLM to pick
    the one most likely to contain company identity pages.
    Returns single sitemap URL or None.
    """
    if len(sitemap_urls) == 1:
        return sitemap_urls[0]

    sitemap_list = "\n".join(sitemap_urls)

    prompt = f"""You are analyzing a company website: {base_url}

Here is the list of available sitemaps:
{sitemap_list}

Which single sitemap is most likely to contain pages about:
- who the company is
- what they do
- "about us", team, company info

Return ONLY the URL of the best sitemap. No explanation, no markdown.
If none seem relevant, return the first one.
"""

    try:
        raw = chat(
            prompt=prompt,
            system="Return ONLY a single URL, nothing else."
        ).strip()
        if raw in sitemap_urls:
            logger.info(f"LLM selected sitemap: {raw}")
            return raw
        logger.warning(f"LLM returned invalid sitemap URL: {raw}")
        return sitemap_urls[0]
    except Exception as e:
        logger.error(f"Sitemap selection failed: {e}")
        return sitemap_urls[0]

def get_relevant_urls(base_url: str) -> list[str]:
    base = base_url.rstrip("/")
    all_candidates = set()

    # source 1 — sitemap
    sitemap_url = find_sitemap_url(base_url)
    if sitemap_url:
        logger.info(f"Fetching sitemap from {sitemap_url}")
        urls = get_sitemap_urls(sitemap_url, base_url=base_url)
        if urls:
            logger.info(f"Found {len(urls)} URLs in sitemap")
            all_candidates.update(urls)

    # source 2 — homepage link extraction
    links = extract_links_from_homepage(base_url)
    if links:
        all_candidates.update(links)

    if not all_candidates:
        logger.warning(f"No candidates found — scraping homepage only")
        return [base_url]

    logger.info(f"Total candidates after merging: {len(all_candidates)}")
    additional = select_relevant_urls(list(all_candidates), base_url)

    if not additional:
        logger.warning(f"LLM found no relevant pages — scraping homepage only")
        return [base_url]

    return [base_url] + additional

if __name__ == "__main__":
    for test_url in ["https://www.fidoo.com/", "https://www.albert.cz", "https://www.alza.cz"]:
        print(f"\n--- {test_url} ---")
        urls = get_relevant_urls(test_url)