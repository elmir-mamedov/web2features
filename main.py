import pandas as pd
import json
import os
from scraper import scrape_company_text
from extractor import extract_company_features, CompanyFeatures
from news_scraper import fetch_company_news, format_news_for_prompt

COMPANIES = [
    {"name": "Fidoo",       "url": "https://www.fidoo.com"},
    {"name": "Revolut",     "url": "https://www.revolut.com"},
    {"name": "Stripe",      "url": "https://www.stripe.com"},
    {"name": "Brex",        "url": "https://www.brex.com"},
    {"name": "Spendesk",    "url": "https://www.spendesk.com"},
    {"name": "Ahold Delhaize", "url": "https://aholddelhaize.com"},
    {"name": "Lasvit",      "url": "https://www.lasvit.com"},
]


def flatten_features(company_name: str, url: str, features: CompanyFeatures) -> dict:
    return {
        "input_name":           company_name,
        "url":                  url,
        "company_name":         features.company_name,
        "industry":             features.industry,
        "hq_country":           features.hq_country,
        "company_size_signal":  features.company_size_signal,
        "main_product":         features.main_product_or_service,
        "target_customer":      features.target_customer,
        "growth_signals":       ", ".join(features.growth_signals),
        "risk_flags":           ", ".join(features.risk_flags),
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

        print(f"[{name}] Fetching news...")
        articles = fetch_company_news(name)
        news_text = format_news_for_prompt(articles)

        print(f"[{name}] Scraped {len(text)} chars + {len(articles)} news articles. Extracting features...")
        features = extract_company_features(text, news=news_text)

        if not features:
            print(f"[{name}] Skipping — extraction failed.")
            continue

        row = flatten_features(name, url, features)
        rows.append(row)
        print(f"[{name}] Done — {features.model_dump_json()}")

    if not rows:
        print("\nNo data extracted.")
        return

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"\nSaved {len(df)} rows to {output_path}")
    print(df.to_string(index=False))


if __name__ == "__main__":
    run_pipeline(COMPANIES)