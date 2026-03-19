# web2features

A lightweight pipeline that converts unstructured company webpage text into 
structured, model-ready features using a local LLM (Ollama).

Built as a proof-of-concept for the kind of external signal extraction used 
in fintech credit scoring and business intelligence.

## What it does

1. **Scrapes** a company's public webpage (`scraper.py`)
2. **Fetches recent news** via Bing News RSS for each company (`news_scraper.py`)
3. **Extracts structured features** from homepage + news via a local LLM prompt (`extractor.py`)
## Output example

| company | industry | size_signal | growth_signals | risk_flags |
|---|---|---|---|---|
| Fidoo | fintech | SME | fundraising, hiring, expansion | |
| Brex | financial technology | enterprise | grew enterprise 80%, AAA bond rating | |
| Ahold Delhaize | retail | enterprise | profit up 55% Q3 | |
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
- News signals are sourced from Bing RSS — descriptions are often short and 
  recent coverage varies by company size. Less-known companies may return 
  irrelevant or sparse results.
- Entity disambiguation is imperfect — companies sharing a name with unrelated 
  entities (e.g. a Czech construction firm named Brex) can pollute news results. 
  Domain-based query helps but does not fully solve this.
- Prompt is English-only optimized — works on Czech but could be improved


## Next steps

- **curl_cffi fallback** — reliable scraping against Cloudflare-protected sites
- **Czech business registry** — scrape Obchodní rejstřík (justice.cz) for 
  authoritative structured data: ICO, legal form, registered capital, founding 
  date, board members, and ownership structure
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