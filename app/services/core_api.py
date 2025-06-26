import logging
import httpx
from asyncio import sleep
from typing import List
from app.config import CORE_API_KEY, CORE_API_URL

logger = logging.getLogger(__name__)

async def fetch_core_articles(query: str, limit: int = 10) -> List[dict]:
    articles: List[dict] = []
    if not CORE_API_KEY:
        logger.warning("CORE_API_KEY not set; skipping CORE fetch.")
        return articles

    headers = {
        "Authorization": f"Bearer {CORE_API_KEY}",
        "Content-Type": "application/json",
    }
    params = {"q": query, "limit": limit, "offset": 0}

    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                resp = await client.get(CORE_API_URL, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()

            # parse out each returned work
            for work in data.get("results", []):
                parts = []
                if abstract := work.get("abstract"):
                    parts.append(abstract)
                if title := work.get("title"):
                    parts.append(title)
                if full := work.get("fullText"):
                    parts.append(full)

                articles.append({
                    "text": " ".join(parts).strip(),
                    "download_url": work.get("downloadUrl"),
                    "title": work.get("title", "Unknown"),
                    "id": work.get("id", ""),
                    "type": "academic",
                })

            # success → break out of retry loop
            break

        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            logger.error(
                f"[CORE API] HTTP {status} on attempt {attempt+1}/3: {e.response.text}"
            )
            # only retry on 5xx
            if status >= 500 and attempt < 2:
                await sleep(1 * (2 ** attempt))
                continue
            else:
                # give up on 4xx or last retry
                break

        except Exception as e:
            logger.exception(f"[CORE API] Unexpected error on attempt {attempt+1}/3")
            if attempt < 2:
                await sleep(1 * (2 ** attempt))
            else:
                break

    return articles
