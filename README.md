# web2features

A lightweight pipeline that converts unstructured company webpage text into 
structured, model-ready features using a local LLM (Ollama).

Built as a proof-of-concept for the kind of external signal extraction used 
in fintech credit scoring and business intelligence.

## What it does

1. **Scrapes** a company's public webpage (`scraper.py`)
2. **Extracts structured features** via a local LLM prompt (`extractor.py`)
3. **Saves** results as a CSV feature table ready for downstream models (`main.py`)

## Output example

| company | industry | size_signal | target_customer | growth_signals |
|---|---|---|---|---|
| Fidoo | Software/Finance | SME | B2B | fundraising, expansion |
| Stripe | Financial Services | enterprise | B2B\|B2C | fundraising, expansion |
| Brex | financial technology | enterprise | B2B | fundraising, hiring |
| Spendesk | Software, Finance | enterprise | B2B | fundraising, hiring |

## Stack

- `requests` + `BeautifulSoup` — scraping and HTML parsing
- `ollama` — local LLM inference (llama3.1:8b)
- `pandas` — feature table output
- No external API keys required — runs fully locally

## Setup
```bash
git clone https://github.com/elmir-mamedov/web2features.git
cd web2features
uv install
ollama pull llama3.1:8b
```

## Usage

Edit the `COMPANIES` list in `main.py`, then:
```bash
python main.py
```

Results are saved to `output/features.csv`.

## Known limitations

- Some sites block plain `requests` (e.g. Revolut → 403) — `curl_cffi` would fix this
- `hq_country` extraction is weak on homepages — a Companies House / Obchodní rejstřík
  scraper would give cleaner data
- Growth signals are inferred, not sourced — adding a news scraper per company
  would make them more reliable
- Prompt is English-only optimized — works on Czech but could be improved

## Next steps

- **curl_cffi fallback** — reliable scraping against Cloudflare-protected sites
- **Multi-page scraping** — scrape `/about` and `/careers` pages per company for richer signal
- **Confidence scores** — rule-based confidence per extracted field so downstream models
  know which features to trust
- **Logprobs** — the theoretically correct way to measure extraction confidence is via
  log probabilities: the model's internal token-level probability distribution exposes
  how sure it was when choosing e.g. "B2B" over "B2C". Ollama exposes logprobs but
  field-level aggregation across multi-token values is non-trivial. Revisit when moving
  to a hosted model with a cleaner logprobs API (e.g. OpenAI).
- **DeepEval integration** — hallucination and faithfulness metrics to verify extracted
  features are actually grounded in the scraped text, not model training memory
- **RAG evolution** — pre-index company documents and news into a vector database
  (e.g. with `nomic-embed-text`) so features can be queried
  instantly rather than scraped on demand — the natural production-scale extension of
  this pipeline