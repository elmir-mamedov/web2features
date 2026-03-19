import sys

import requests
from bs4 import BeautifulSoup
import re
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

    # ICO numbers appear as "IČO: XXXXXXXX" in search results
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

    # find the "Výpis platných" link which contains subjektId
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


def scrape_registry(subjekt_id: str, ico: str = "") -> dict:
    """
    Scrape current registry extract from justice.cz by subjektId.
    """
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

    def extract(pattern: str) -> str | None:
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    # founding date
    founded = extract(r"Datum vzniku a zápisu:\s+(\d+\.\s+\w+\s+\d{4})")

    # legal form
    legal_form = extract(r"Právní forma:\s+([^\n]+?)(?=\s+Předmět|\s+Sídlo|\s+Identifikační)")

    # address
    address = extract(r"Sídlo:\s+([^I]+?)(?=Identifikační číslo)")

    # registered capital
    capital = extract(r"Základní kapitál:\s+([\d\s]+,-\s*Kč)")

    # parent company
    parent = extract(r"Jediný akcionář:\s+(.+?)(?=\s+Akcie:|$)")

    # current board members — find names after správní rada or představenstvo
    board = re.findall(
        r"(?:předseda|člen)\s+(?:správní rady|představenstva):\s+([A-ZÁČĎÉĚÍŇÓŘŠŤÚŮÝŽ][^\n,]+?)(?=\s*,\s*dat\.)",
        text,
        re.IGNORECASE
    )

    # last change — look for the date at the bottom
    last_change = extract(r"Údaje platné ke dni\s+(\d+\.\d+\.\d+)")

    return {
        "ico":            ico,
        "justice.cz subjektId": subjekt_id,
        "legal_form":     legal_form.strip() if legal_form else None,
        "founded":        founded,
        "address":        address.strip() if address else None,
        "capital_czk":    capital.strip() if capital else None,
        "parent_company": parent.strip() if parent else None,
        "board_members":  board,
        "last_change":    last_change,
        "registry_url":   url,
    }


def get_registry_data(ico: str) -> dict:
    """
    Main entry point — look up company by ICO and return registry data.
    """
    logger.info(f"Looking up registry data for ICO: {ico}")

    subjekt_id = get_subjekt_id(ico)
    if not subjekt_id:
        return {}

    return scrape_registry(subjekt_id, ico=ico)


if __name__ == "__main__":
    import json
    ico = search_ico("Direct Group")
    data = get_registry_data(ico)
    print(json.dumps(data, ensure_ascii=False, indent=2))