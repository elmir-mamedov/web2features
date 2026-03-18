import requests
from bs4 import BeautifulSoup
import re
from logger import setup_logger

logger = setup_logger()


def fetch_company_news(company_name: str, company_url: str = "", max_articles: int = 10) -> list[dict]:
    domain = company_url.replace("https://www.", "").replace("https://", "").split("/")[0].split(".")[0]
    query = f"{company_name} {domain}".strip().replace(" ", "+") if domain else company_name
    url = f"https://www.bing.com/news/search?q={query}&format=rss" # Using company url in query reduces entity ambiguity

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Failed to fetch news for {company_name}: {e}")
        #print(f"[news] Failed to fetch news for {company_name}: {e}")
        return []

    soup = BeautifulSoup(response.text, "xml")
    items = soup.find_all("item")[:max_articles]

    articles = []
    for item in items:
        title = item.title.text.strip() if item.title else ""

        # description contains raw HTML — parse it to extract clean text
        raw_description = item.description.text if item.description else ""
        desc_soup = BeautifulSoup(raw_description, "html.parser")
        clean_description = desc_soup.get_text(separator=" ", strip=True)
        # collapse whitespace
        clean_description = re.sub(r"\s+", " ", clean_description).strip()

        articles.append({
            "title":       title,
            "description": clean_description[:200],
            "published":   item.pubDate.text.strip() if item.pubDate else "",
            "source": item.find("News:Source").text.strip() if item.find("News:Source") else "",
        })

    return articles


def format_news_for_prompt(articles: list[dict]) -> str:
    """
    Formats news articles into a clean string to append to the LLM prompt.
    """
    if not articles:
        return "No recent news found."

    lines = []
    for i, article in enumerate(articles, 1):
        lines.append(f"{i}. [{article['source']}] {article['title']} ({article['published']})")
        if article["description"]:
            lines.append(f"   {article['description']}")

    return "\n".join(lines)


if __name__ == "__main__":
    company_name = "Ahold Delhaize"
    company_url = "https://aholddelhaize.com"
    print(f"Fetching news for {company_name}...\n")

    articles = fetch_company_news(company_name, company_url=company_url)
    print(format_news_for_prompt(articles))