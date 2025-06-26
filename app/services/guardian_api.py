import httpx
import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional

from app.config import GUARDIAN_API_KEY, GUARDIAN_API_URL

logger = logging.getLogger(__name__)

def strip_html(html: str) -> str:
    # simple HTML‐to‐text; for more robust needs consider BeautifulSoup
    return re.sub(r"<[^>]+>", "", html)

async def fetch_guardian_all_pages(
    query: str,
    days_back: int = 30,
    page_size: int = 15,
    max_pages: Optional[int] = 2
) -> List[dict]:
    """
    Fetches all pages of Guardian search results via /search and then /content/{id}/next,
    returns list of dicts with plain‐text body under 'text'.
    """
    if not GUARDIAN_API_KEY:
        logger.warning("GUARDIAN_API_KEY not set; skipping Guardian fetch.")
        return []

    to_date   = datetime.utcnow().date()
    from_date = to_date - timedelta(days=days_back)
    params = {
        "q":           query,
        "from-date":   from_date.isoformat(),
        "to-date":     to_date.isoformat(),
        "page-size":   page_size,
        "show-fields": "body",
        "order-by":    "relevance",
        "api-key":     GUARDIAN_API_KEY,
    }

    articles: List[dict] = []
    async with httpx.AsyncClient(timeout=20) as client:
        # 1) initial /search
        resp = await client.get(GUARDIAN_API_URL, params=params)
        resp.raise_for_status()
        data    = resp.json().get("response", {})
        results = data.get("results", [])

        for r in results:
            html = r.get("fields", {}).get("body", "")
            articles.append({
                "text":  strip_html(html),
                "title": r.get("webTitle", ""),
                "url":   r.get("webUrl", ""),
                "date":  r.get("webPublicationDate", ""),
                "type":  "news",
            })

        # 2) deep‐paginate via /content/{last_id}/next
        pages_fetched = 1
        last_id = results[-1]["id"] if results else None

        while last_id and (max_pages is None or pages_fetched < max_pages):
            next_url = f"https://content.guardianapis.com/content/{last_id}/next"
            resp = await client.get(next_url, params={
                "q":         query,
                "page-size": page_size,
                "order-by":  params["order-by"],
                "api-key":   GUARDIAN_API_KEY,
            })
            resp.raise_for_status()
            data         = resp.json().get("response", {})
            next_results = data.get("results", [])
            if not next_results:
                break

            for r in next_results:
                html = r.get("fields", {}).get("body", "")
                articles.append({
                    "text":  strip_html(html),
                    "title": r.get("webTitle", ""),
                    "url":   r.get("webUrl", ""),
                    "date":  r.get("webPublicationDate", ""),
                    "type":  "news",
                })

            last_id       = next_results[-1]["id"]
            pages_fetched += 1
            if len(next_results) < page_size:
                break

    return articles
