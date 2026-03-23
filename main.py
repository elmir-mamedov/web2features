import pandas as pd
import json
import os
from company_website_scraper import scrape_company_text
from sitemap_scraper import get_relevant_urls
from company_website_scraper import scrape_multiple_urls
from extractor import extract_company_features, CompanyFeatures
from news_scraper import fetch_company_news, format_news_for_prompt
from logger import setup_logger
from datetime import datetime
import argparse
from registry_scraper import get_registry_data


logger = setup_logger()

COMPANIES = [
    {"name": "Fidoo",       "url": "https://www.fidoo.com"},
    {"name": "Albert", "url": "https://www.albert.cz/"},
    {"name": "Alza",        "url": "https://www.alza.cz"},
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
    os.makedirs("logs", exist_ok=True)
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = []
    registry_rows = []
    news_log = []

    for company in companies:
        name = company["name"]
        url  = company["url"]
        ico  = company.get("ico") or None  # optional field

        logger.info(f"[{name}] Scraping {url} ...")
        urls_to_scrape = get_relevant_urls(url)
        text = scrape_multiple_urls(urls_to_scrape)
        if not text:
            logger.warning(f"[{name}] Skipping — nothing scraped.")
            continue

        logger.info(f"[{name}] Fetching news...")
        articles = fetch_company_news(name, company_url=url)
        news_text = format_news_for_prompt(articles)

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

        # registry lookup — only attempt for Czech companies
        logger.info(f"[{name}] Looking up registry...")
        registry_data = get_registry_data(features.company_name or name, ico=ico)
        if registry_data:
            registry_rows.append({
                "input_name": name,
                **registry_data
            })
            logger.info(f"[{name}] Registry data found — ICO {registry_data.get('ico')}")
        else:
            logger.info(f"[{name}] No registry data found — skipping.")

    if not rows:
        logger.warning("No data extracted.")
        return

    # save features CSV
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df)} rows to {output_path}")

    # save registry CSV
    if registry_rows:
        registry_df = pd.DataFrame(registry_rows)
        registry_path = output_path.replace("features.csv", "registry.csv")
        registry_df.to_csv(registry_path, index=False)
        logger.info(f"Saved {len(registry_df)} registry rows to {registry_path}")

    # save news log
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
        if not os.path.exists(args.input):
            logger.error(f"Input file not found: {args.input}")
            exit(1)
        input_df = pd.read_csv(args.input)
        if not {"name", "url"}.issubset(input_df.columns):
            logger.error("Input CSV must have 'name' and 'url' columns")
            exit(1)
        # ico column is optional — fill missing with empty string
        if "ico" not in input_df.columns:
            input_df["ico"] = ""
        input_df["ico"] = input_df["ico"].fillna("").astype(str)
        companies = input_df[["name", "url", "ico"]].to_dict(orient="records")
        logger.info(f"CSV input mode: {len(companies)} companies from {args.input}")

    else:
        # default mode — use hardcoded COMPANIES list
        companies = COMPANIES
        logger.info(f"Default mode: {len(companies)} hardcoded companies")

    run_pipeline(companies, output_path=args.output)