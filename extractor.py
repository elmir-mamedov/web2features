import ollama
import json
import re


EXTRACTION_PROMPT = """You are a business intelligence analyst. Extract structured information from the company webpage text below.

Return ONLY a valid JSON object with exactly these fields:
{{
  "company_name": "string or null",
  "industry": "string or null",
  "hq_country": "string or null",
  "company_size_signal": "startup | SME | enterprise | unknown",
  "main_product_or_service": "string, max 15 words",
  "target_customer": "B2B | B2C | both | unknown",
  "growth_signals": ["list of short strings, or empty list"],
  "risk_flags": ["list of short strings, or empty list"],
  "language": "language of the webpage text"
}}

Rules:
- Return ONLY the JSON. No explanation, no markdown, no code blocks.
- If you are not sure about a field, use null or "unknown".
- growth_signals: things like fundraising, hiring, expansion, new products.
- risk_flags: things like layoffs, lawsuits, losses, restructuring.

Webpage text:
{text}
"""


def extract_company_features(text: str, model: str = "llama3.1:8b") -> dict:
    """
    Sends scraped text to local Ollama model and returns structured features.
    """
    if not text:
        return {}

    prompt = EXTRACTION_PROMPT.format(text=text)

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0}  # deterministic output
        )
        raw = response.message.content.strip()

        # Sometimes models wrap JSON in markdown — strip it just in case
        raw = re.sub(r"^```json\s*", "", raw)
        raw = re.sub(r"^```\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)

        return json.loads(raw)

    except json.JSONDecodeError as e:
        print(f"[extractor] JSON parse failed: {e}")
        print(f"[extractor] Raw output was:\n{raw}")
        return {}
    except Exception as e:
        print(f"[extractor] Ollama error: {e}")
        return {}


if __name__ == "__main__":
    from scraper import scrape_company_text

    url = "https://www.fidoo.com"
    text = scrape_company_text(url)
    print("Extracting features...\n")

    features = extract_company_features(text)
    print(json.dumps(features, indent=2, ensure_ascii=False))