import ollama
import json
import re
from pydantic import BaseModel, field_validator
from typing import Literal
from logger import setup_logger

logger = setup_logger()


class CompanyFeatures(BaseModel):
    company_name: str | None = None
    industry: str | None = None
    hq_country: str | None = None
    company_size_signal: Literal["startup", "SME", "enterprise", "unknown"] = "unknown"
    main_product_or_service: str | None = None
    target_customer: Literal["B2B", "B2C", "both", "unknown"] = "unknown"
    growth_signals: list[str] = []
    risk_flags: list[str] = []

    @field_validator("growth_signals", "risk_flags", mode="before")
    @classmethod
    def coerce_to_list(cls, v):
        """
        If the LLM returns a string instead of a list, convert it.
        e.g. "hiring, expansion" -> ["hiring", "expansion"]
        e.g. "none" -> []
        e.g. null -> []
        """
        if v is None:
            return []
        if isinstance(v, str):
            if v.lower() in ("none", "null", "n/a", ""):
                return []
            return [item.strip() for item in v.split(",")]
        return v

    @field_validator("company_size_signal", mode="before")
    @classmethod
    def normalize_size(cls, v):
        """
        Catch variations like 'small-medium', 'large', 'mid-size' etc.
        and map them to our allowed values.
        """
        if not isinstance(v, str):
            return "unknown"
        v = v.lower().strip()
        if any(x in v for x in ["startup", "early"]):
            return "startup"
        if any(x in v for x in ["sme", "small", "medium", "mid"]):
            return "SME"
        if any(x in v for x in ["enterprise", "large", "corporate"]):
            return "enterprise"
        return "unknown"

    @field_validator("target_customer", mode="before")
    @classmethod
    def normalize_target(cls, v):
        """
        Catch variations like 'B2B | B2C', 'business', 'consumers' etc.
        """
        if not isinstance(v, str):
            return "unknown"
        v_lower = v.lower().strip()
        has_b2b = "b2b" in v_lower or "business" in v_lower
        has_b2c = "b2c" in v_lower or "consumer" in v_lower or "individual" in v_lower
        if has_b2b and has_b2c:
            return "both"
        if has_b2b:
            return "B2B"
        if has_b2c:
            return "B2C"
        return "unknown"


EXTRACTION_PROMPT = """You are a business intelligence analyst. Extract structured information from the data below.

You have two sources:
1. HOMEPAGE TEXT — describes what the company does
2. RECENT NEWS — headlines about the company from the last 90 days

Use both sources together. News is especially useful for growth_signals and risk_flags
since companies never report bad news on their own homepage.

Return ONLY a valid JSON object with exactly these fields:
{{
  "company_name": "string or null",
  "industry": "string or null",
  "hq_country": "string or null",
  "company_size_signal": "startup | SME | enterprise | unknown",
  "main_product_or_service": "string, max 15 words",
  "target_customer": "B2B | B2C | both | unknown",
  "growth_signals": ["list of short strings, or empty list"],
  "risk_flags": ["list of short strings, or empty list"]
}}

Rules:
- Return ONLY the JSON. No explanation, no markdown, no code blocks.
- If you are not sure about a field, use null or "unknown".
- growth_signals: things like fundraising, hiring, expansion, acquisition, new products.
- risk_flags: things like layoffs, lawsuits, losses, restructuring, valuation drop.

--- HOMEPAGE TEXT ---
{text}

--- RECENT NEWS ---
{news}
"""


def extract_company_features(
    text: str,
    news: str = "No recent news found.",
    model: str = "llama3.1:8b"
) -> CompanyFeatures | None:
    """
    Sends scraped homepage text + recent news to local Ollama model
    and returns a validated CompanyFeatures object, or None if extraction failed.
    """
    if not text:
        return None

    prompt = EXTRACTION_PROMPT.format(text=text, news=news)

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0}
        )
        raw = response.message.content.strip()

        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        logger.debug(f"Raw LLM output: {raw}")
        data = json.loads(raw)
        return CompanyFeatures(**data)

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed: {e}")
        #print(f"[extractor] JSON parse failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        #print(f"[extractor] Error: {e}")
        return None


if __name__ == "__main__":
    from scraper import scrape_company_text

    url = "https://www.fidoo.com"
    text = scrape_company_text(url)
    print("Extracting features...\n")

    features = extract_company_features(text)
    if features:
        print(features.model_dump_json(indent=2))