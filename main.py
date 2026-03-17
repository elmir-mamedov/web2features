import pandas as pd
import json
import os
from scraper import scrape_company_text
from extractor import extract_company_features

COMPANIES = [
    {"name": "Fidoo",       "url": "https://www.fidoo.com"},
    {"name": "Revolut",     "url": "https://www.revolut.com"},
    {"name": "Stripe",      "url": "https://www.stripe.com"},
    {"name": "Brex",        "url": "https://www.brex.com"},
    {"name": "Spendesk",    "url": "https://www.spendesk.com"},
]


def flatten_features(company_name: str, url: str, features: dict) -> dict:
    """
    Flattens nested lists into strings so the row fits neatly in a CSV.
    """
    return {
        "input_name":           company_name,
        "url":                  url,
        "company_name":         features.get("company_name"),
        "industry":             features.get("industry"),
        "hq_country":           features.get("hq_country"),
        "company_size_signal":  features.get("company_size_signal"),
        "main_product":         features.get("main_product_or_service"),
        "target_customer":      features.get("target_customer"),
        "growth_signals":       ", ".join(features.get("growth_signals", [])),
        "risk_flags":           ", ".join(features.get("risk_flags", [])),
        "language":             features.get("language"),
    }


def run_pipeline(companies: list, output_path: str = "output/features.csv"):
    os.makedirs("output", exist_ok=True)
    rows = []

    for company in companies:
        name = company["name"]
        url  = company["url"]
        print(f"\n[{name}] Scraping {url} ...")

        text = scrape_company_text(url)
        if not text:
            print(f"[{name}] Skipping — nothing scraped.")
            continue

        print(f"[{name}] Scraped {len(text)} chars. Extracting features...")
        features = extract_company_features(text)

        if not features:
            print(f"[{name}] Skipping — extraction failed.")
            continue

        row = flatten_features(name, url, features)
        rows.append(row)
        print(f"[{name}] Done — {json.dumps(features, ensure_ascii=False)}")

    if not rows:
        print("\nNo data extracted.")
        return

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"\nSaved {len(df)} rows to {output_path}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    run_pipeline(COMPANIES)