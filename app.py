import json
from flask import Flask, render_template, request, Response, stream_with_context
from scraper import scrape_company_text
from extractor import extract_company_features
from news_scraper import fetch_company_news, format_news_for_prompt
from registry_scraper import get_registry_data
import ollama

def check_ollama() -> bool:
    """Check if Ollama is running and llama3.1:8b is available."""
    try:
        models = ollama.list()
        available = [m.model for m in models.models]
        return any("llama3.1" in m for m in available)
    except Exception:
        return False


app = Flask(__name__)



def stream_pipeline(name: str, url: str, ico: str = ""):
    """
    Generator function that runs the pipeline and yields SSE events.
    Each event is a JSON object with type and data fields.
    """
    def event(event_type: str, data: dict) -> str:
        return f"data: {json.dumps({'type': event_type, 'data': data})}\n\n"

    # check ollama first
    if not check_ollama():
        yield event("error", {
            "message": "Ollama is not running or llama3.1:8b is not installed. "
                       "Start Ollama and run: ollama pull llama3.1:8b"
        })
        return

    # step 1 — scrape
    yield event("status", {"message": f"Scraping {url}..."})
    text = scrape_company_text(url)
    if not text:
        yield event("error", {"message": f"Failed to scrape {url}"})
        return
    yield event("status", {"message": f"Scraped {len(text)} characters"})

    # step 2 — news
    yield event("status", {"message": "Fetching recent news..."})
    articles = fetch_company_news(name, company_url=url)
    news_text = format_news_for_prompt(articles)
    yield event("status", {"message": f"Found {len(articles)} news articles"})

    # step 3 — LLM extraction
    yield event("status", {"message": "Extracting features with LLM..."})
    features = extract_company_features(text, news=news_text)
    if not features:
        yield event("error", {"message": "LLM extraction failed"})
        return
    yield event("features", {"data": features.model_dump()})
    yield event("status", {"message": "Features extracted successfully"})

    # step 4 — registry
    yield event("status", {"message": "Looking up Czech business registry..."})
    registry = get_registry_data(name, ico=ico if ico else None)
    if registry:
        yield event("registry", {"data": registry})
        yield event("status", {"message": f"Registry data found — ICO {registry.get('ico')}"})
    else:
        yield event("status", {"message": "No registry data found — skipping"})

    yield event("done", {"message": "Pipeline complete"})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    name = request.form.get("name", "").strip()
    url = request.form.get("url", "").strip()
    ico = request.form.get("ico", "").strip()

    if not name or not url:
        return {"error": "Name and URL are required"}, 400

    return Response(
        stream_with_context(stream_pipeline(name, url, ico)),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)