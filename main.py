import pandas as pd
import json
import os
from scraper import scrape_company_text
from extractor import extract_company_features, CompanyFeatures
from news_scraper import fetch_company_news, format_news_for_prompt
from logger import setup_logger
from datetime import datetime
import argparse

logger = setup_logger()

COMPANIES = [
    {"name": "Fidoo",       "url": "https://www.fidoo.com"},
    {"name": "Ahold Delhaize", "url": "https://aholddelhaize.com"},
]

def parse_args():
    parser = argparse.ArgumentParser(
        description="web2features — extract structured company intelligence from the web"
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--url",
        type=str,
        help="scrape a single company URL e.g. --url https://www.fidoo.com"
    )
    group.add_argument(
        "--input",
        type=str,
        help="path to a CSV file with 'name' and 'url' columns e.g. --input companies.csv"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="output/features.csv",
        help="path to output CSV file (default: output/features.csv)"
    )

    return parser.parse_args()

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
    os.makedirs("logs", exist_ok=True)  # add this
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = []
    news_log = []  # collect all news records here

    for company in companies:
        name = company["name"]
        url  = company["url"]
        logger.info(f"[{name}] Scraping {url} ...")

        text = scrape_company_text(url)
        if not text:
            logger.warning(f"[{name}] Skipping — nothing scraped.")
            continue

        logger.info(f"[{name}] Fetching news...")
        articles = fetch_company_news(name, company_url=url)
        news_text = format_news_for_prompt(articles)

        # collect news record
        news_log.append({
            "company": name,
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "article_count": len(articles),
            "articles": articles
        })

        logger.info(f"[{name}] Scraped {len(text)} chars + {len(articles)} news articles. Extracting features...")
        features = extract_company_features(text, news=news_text)

        if not features:
            logger.warning(f"[{name}] Skipping — extraction failed.")
            continue

        row = flatten_features(name, url, features)
        rows.append(row)
        logger.info(f"[{name}] Done — {features.model_dump_json()}")

    if not rows:
        logger.warning("No data extracted.")
        return

    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df)} rows to {output_path}")

    # save news log as pretty JSON
    news_log_path = os.path.join("logs", f"news_{run_id}.json")
    with open(news_log_path, "w", encoding="utf-8") as f:
        json.dump({
            "run_id": run_id,
            "company_count": len(news_log),
            "companies": news_log
        }, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved news log to {news_log_path}")

if __name__ == "__main__":
    args = parse_args()

    if args.url:
        # single URL mode — extract company name from domain
        domain = args.url.replace("https://www.", "").replace("https://", "").split(".")[0]
        companies = [{"name": domain.capitalize(), "url": args.url}]
        logger.info(f"Single URL mode: {args.url}")

    elif args.input:
        # CSV input mode
        if not os.path.exists(args.input):
            logger.error(f"Input file not found: {args.input}")
            exit(1)
        input_df = pd.read_csv(args.input)
        if not {"name", "url"}.issubset(input_df.columns):
            logger.error("Input CSV must have 'name' and 'url' columns")
            exit(1)
        companies = input_df[["name", "url"]].to_dict(orient="records")
        logger.info(f"CSV input mode: {len(companies)} companies from {args.input}")

    else:
        # default mode — use hardcoded COMPANIES list
        companies = COMPANIES
        logger.info(f"Default mode: {len(companies)} hardcoded companies")

    run_pipeline(companies, output_path=args.output)