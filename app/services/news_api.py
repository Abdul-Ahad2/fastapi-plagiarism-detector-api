import logging
from datetime import datetime, timedelta
import httpx
from typing import List
from app.config import NEWS_API_KEY, NEWS_API_URL

logger = logging.getLogger(__name__)

async def fetch_news_articles(query: str, days_back: int = 30, page_size: int = 15) -> List[dict]:
    articles = []
    if not NEWS_API_KEY:
        return articles

    to_date = datetime.utcnow()
    from_date = to_date - timedelta(days=days_back)
    params = {
        "q": query,
        "from": from_date.strftime("%Y-%m-%d"),
        "to": to_date.strftime("%Y-%m-%d"),
        "pageSize": page_size,
        "sortBy": "relevancy",
        "apiKey": NEWS_API_KEY,
    }

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(NEWS_API_URL, params=params)
            resp.raise_for_status()
            data = resp.json()
            if data.get("status") == "ok":
                for a in data.get("articles", []):
                    content = ""
                    if a.get("content"):
                        content += a["content"]
                    if a.get("description"):
                        content += " " + a["description"]
                    if a.get("title"):
                        content += " " + a["title"]
                    articles.append(
                        {
                            "text": content.strip(),
                            "url": a.get("url", ""),
                            "title": a.get("title", "Unknown"),
                            "type": "news",
                        }
                    )
        except Exception as e:
            logger.error(f"Error fetching News API: {e}")
    return articles
