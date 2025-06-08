import logging
import httpx
from typing import List
from app.config import CORE_API_KEY, CORE_API_URL

logger = logging.getLogger(__name__)

async def fetch_core_articles(query: str, limit: int = 15) -> List[dict]:
    articles = []
    if not CORE_API_KEY:
        return articles

    headers = {"Authorization": f"Bearer {CORE_API_KEY}", "Content-Type": "application/json"}
    params = {"q": query, "limit": limit, "offset": 0}

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(CORE_API_URL, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            for work in data.get("results", []):
                content = ""
                if work.get("abstract"):
                    content += work["abstract"]
                if work.get("title"):
                    content += " " + work["title"]
                if work.get("fullText"):
                    content += " " + work["fullText"]
                articles.append(
                    {
                        "text": content.strip(),
                        "download_url": work.get("downloadUrl"),
                        "title": work.get("title", "Unknown"),
                        "id": work.get("id", ""),
                        "type": "academic",
                    }
                )
        except Exception as e:
            logger.error(f"Error fetching CORE API: {e}")
    return articles
