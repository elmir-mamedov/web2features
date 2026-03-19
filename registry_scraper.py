import requests
import ollama
import json
import re
from bs4 import BeautifulSoup
from logger import setup_logger

logger = setup_logger()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

SEARCH_ICO_URL = "https://rejstrik-firem.kurzy.cz/hledej/?s={query}&r=True"
SEARCH_SUBJECT_ID_URL = "https://or.justice.cz/ias/ui/rejstrik-$firma?ico={ico}"
DETAIL_URL = "https://or.justice.cz/ias/ui/rejstrik-firma.vysledky?subjektId={subjekt_id}&typ=PLATNY"

REGISTRY_PROMPT = """You are a Czech business registry analyst. Extract structured information from the official Czech business registry extract below.

Return ONLY a valid JSON object with exactly these fields:
{{
  "legal_form": "string or null — e.g. 'Akciová společnost', 'Společnost s ručením omezeným'",
  "founded": "string or null — founding date in original Czech format e.g. '10. února 2012'",
  "address": "string or null — current registered address only",
  "parent_company": "string or null — name of sole shareholder or majority owner if present",
  "board_members": [
    {{"name": "string — full name only", "role": "string — their role e.g. předseda představenstva"}}
],
  "recent_changes": ["list of recent structural changes e.g. board changes, mergers, capital increases, or empty list"]
}}

Rules:
- Return ONLY the JSON. No explanation, no markdown, no code blocks.
- Extract CURRENT data only — ignore historical entries.
- board_members should include jednatelé, předseda/člen představenstva, předseda/člen správní rady — whoever is the current statutory body. Include role titles 
- recent_changes: look for mergers (fúze), acquisitions, capital increases, board restructuring. Always include the year in which the change had occured if it's the year is present in the text.
- For parent_company: look for 'Jediný akcionář' or the main 'Společník' with 100% share.

Registry text:
{text}
"""


def search_ico(company_name: str) -> str | None:
    """
    Search kurzy.cz registry by company name, return first ICO found.
    """
    url = SEARCH_ICO_URL.format(query=company_name.replace(" ", "+"))

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Registry search failed for {company_name}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    ico_match = re.search(r"IČO:\s*(\d{8})", soup.get_text())
    if ico_match:
        ico = ico_match.group(1)
        logger.debug(f"Found ICO {ico} for {company_name}")
        return ico

    logger.warning(f"No ICO found for {company_name}")
    return None


def get_subjekt_id(ico: str) -> str | None:
    """
    Search justice.cz by ICO and extract subjektId from the result page.
    """
    url = SEARCH_SUBJECT_ID_URL.format(ico=ico)

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Registry search failed for ICO {ico}: {e}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    link = soup.find("a", string="Výpis platných")
    if not link:
        logger.warning(f"No registry result found for ICO {ico}")
        return None

    href = link.get("href", "")
    match = re.search(r"subjektId=(\d+)", href)
    if not match:
        logger.warning(f"Could not extract subjektId from href: {href}")
        return None

    subjekt_id = match.group(1)
    logger.debug(f"Found subjektId {subjekt_id} for ICO {ico}")
    return subjekt_id


def scrape_and_extract(subjekt_id: str, ico: str = "", model: str = "llama3.1:8b") -> dict:
    url = DETAIL_URL.format(subjekt_id=subjekt_id)

    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Registry detail fetch failed for subjektId {subjekt_id}: {e}")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    text = soup.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)

    cutoff = text.find("Stáhnout PDF")
    if cutoff > 0:
        text = text[:cutoff]

    # regex for capital — LLMs are unreliable with numbers
    capital_czk = None
    capital_match = re.search(r"Základní kapitál:\s*([\d\s]+),-\s*Kč", text)
    if capital_match:
        capital_czk = int(capital_match.group(1).replace(" ", ""))
        logger.debug(f"Regex extracted capital: {capital_czk}")

    # LLM for everything else
    prompt = REGISTRY_PROMPT.format(text=text)
    try:
        llm_response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0}
        )
        raw = llm_response.message.content.strip()
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        extracted = json.loads(raw)
        logger.debug(f"LLM extracted: {extracted}")
    except json.JSONDecodeError as e:
        logger.error(f"Registry JSON parse failed: {e}")
        extracted = {}
    except Exception as e:
        logger.error(f"Registry LLM extraction failed: {e}")
        extracted = {}

    # filter recent_changes to only keep entries mentioning 2024 or 2025
    if "recent_changes" in extracted:
        extracted["recent_changes"] = [
            c for c in extracted["recent_changes"]
            if any(year in c for year in ["2024", "2025", "2026"])
        ]

    # regex value overrides LLM value for capital
    if capital_czk is not None:
        extracted["capital_czk"] = capital_czk

    return {
        "ico":          ico,
        "subjekt_id":   subjekt_id,
        "registry_url": url,
        **extracted
    }


def get_registry_data(company_name: str, ico: str | None = None) -> dict:
    """
    Main entry point.
    If ICO is provided, use it directly.
    Otherwise search by company name.
    Returns empty dict if company not found in Czech registry.
    """
    if not ico:
        logger.info(f"[registry] Searching ICO for: {company_name}")
        ico = search_ico(company_name)

    if not ico:
        logger.warning(f"[registry] No ICO found for {company_name} — skipping registry lookup")
        return {}

    logger.info(f"[registry] Fetching registry data for ICO: {ico}")
    subjekt_id = get_subjekt_id(ico)
    if not subjekt_id:
        return {}

    return scrape_and_extract(subjekt_id, ico=ico)


if __name__ == "__main__":
    # test with Fidoo by name
    data = get_registry_data("Alza")
    print(json.dumps(data, ensure_ascii=False, indent=2))