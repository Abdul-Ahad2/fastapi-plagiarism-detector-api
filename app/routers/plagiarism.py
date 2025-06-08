import json
from pathlib import Path
from datetime import datetime
from typing import List, Optional

import asyncio
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from jose import jwt, JWTError

from app.models.schemas import (
    SentenceResult,
    MatchDetail,
    ReportDetail,        # ← import ReportDetail instead of PlagiarismResponse
)
from app.services.news_api import fetch_news_articles
from app.services.core_api import fetch_core_articles
from app.utils.file_utils import extract_text_from_file, allowed_file
from app.utils.text_utils import (
    normalize_text,
    get_meaningful_sentences,
    extract_keywords,
    find_exact_matches,
    find_partial_phrase_match,
    extract_full_text_from_news_article,
    extract_full_text_from_pdf_url,
)
from app.config import MIN_SENTENCE_LENGTH, MONGODB_URI

router = APIRouter()

# ───── JWT setup ─────
SECRET_KEY = "123"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

# ───── MongoDB client dependency ─────
async def get_mongo_client():
    return AsyncIOMotorClient(MONGODB_URI)


@router.post(
    "/plagiarism/check",
    response_model=ReportDetail,
    dependencies=[Depends(verify_token)]
)
async def check_plagiarism(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client),
    token_payload: dict = Depends(verify_token),
):
    """
    1) Run the plagiarism pipeline exactly as before.
    2) Insert one document into MongoDB 'reports' collection containing:
       - user_id, name, content, date, similarity, sources, word_count, time_spent, flagged, plagiarism_data
    3) Return a ReportDetail:
       {
         id: <inserted ObjectId as string>,
         name: <filename or generated title>,
         content: <raw_text>,
         plagiarism_data: [ ...flat list of MatchDetail dicts... ]
       }
    """
    db = mongo_client.get_default_database()
    reports_collection = db["reports"]

    # 1. Extract raw text from file or form
    if file and file.filename:
        if not allowed_file(file.filename):
            raise HTTPException(status_code=400, detail="Invalid file type.")
        content_bytes = await file.read()
        raw_text = extract_text_from_file(content_bytes, file.filename)
        title = file.filename
    elif text and text.strip():
        raw_text = text
        title = "pasted_text_" + datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    else:
        raise HTTPException(status_code=400, detail="No file or text provided.")

    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="No readable text found.")

    # 2. Split into meaningful sentences
    sentences = get_meaningful_sentences(raw_text)
    if not sentences:
        # If there are no sentences, we can still store an “empty” report or raise.
        # Here, let’s insert an empty‐results report in Mongo and return it.
        empty_doc = {
            "user_id": token_payload.get("id"),
            "name": title,
            "content": raw_text,
            "date": datetime.utcnow(),
            "similarity": 0.0,
            "sources": [],
            "word_count": len(raw_text.split()),
            "time_spent": "00:00",
            "flagged": False,
            "plagiarism_data": [],
        }
        insert_result = await reports_collection.insert_one(empty_doc)
        return ReportDetail(
            id=str(insert_result.inserted_id),
            name=title,
            content=raw_text,
            plagiarism_data=[]
        )

    # 3. Extract keywords
    keywords = extract_keywords(raw_text, max_keywords=5)
    query = " ".join(keywords) if keywords else raw_text[:100]

    # 4. Fetch News & CORE data concurrently
    news_task = fetch_news_articles(query)
    core_task = fetch_core_articles(query)
    news_articles, core_works = await asyncio.gather(news_task, core_task)

    external_texts = []

    # 5. Process News API results
    for art in news_articles:
        content = art.get("text", "")
        if not content.strip() and art.get("url"):
            scraped = extract_full_text_from_news_article(art["url"])
            content = scraped
        if content.strip():
            external_texts.append({
                "text": content,
                "title": art.get("title", ""),
                "source_url": art.get("url", ""),
                "type": "news",
            })

    # 6. Process CORE API results
    for work in core_works:
        content = work.get("text", "")
        if not content.strip() and work.get("download_url"):
            content = await extract_full_text_from_pdf_url(work["download_url"])
        if not content.strip() and work.get("abstract"):
            content = work["abstract"]
        if content.strip():
            external_texts.append({
                "text": content,
                "title": work.get("title", ""),
                "source_url": str(work.get("id", "")),
                "type": "academic",
            })

    # 7. If no external_texts → all “no match”
    if not external_texts:
        plagiarism_data_for_db: List[dict] = []
        report_doc = {
            "user_id": token_payload.get("id"),
            "name": title,
            "content": raw_text,
            "date": datetime.utcnow(),
            "similarity": 0.0,
            "sources": [],
            "word_count": len(raw_text.split()),
            "time_spent": "00:00",
            "flagged": False,
            "plagiarism_data": plagiarism_data_for_db,
        }
        insert_result = await reports_collection.insert_one(report_doc)
        return ReportDetail(
            id=str(insert_result.inserted_id),
            name=title,
            content=raw_text,
            plagiarism_data=[]
        )

    # 8. Normalize external texts
    for ext in external_texts:
        ext["normalized_text"] = normalize_text(ext["text"])

    # 9. Compare each sentence against external texts
    plagiarism_data_for_db: List[dict] = []
    highest_similarity = 0.0
    all_matched_titles = set()

    for orig in sentences:
        # Check full‐sentence matches first
        matched_this_sentence = False
        for ext in external_texts:
            sim = find_exact_matches(orig, ext["text"])
            if sim is not None:
                similarity = round(sim, 3)
                plagiarism_data_for_db.append({
                    "matched_text": orig,
                    "similarity": similarity,
                    "source_type": ext["type"],
                    "source_title": ext["title"],
                    "source_url": ext["source_url"],
                })
                matched_this_sentence = True
                if sim > highest_similarity:
                    highest_similarity = sim
                all_matched_titles.add(ext["title"])
                break

        # If no full‐sentence match, do partial‐phrase
        if not matched_this_sentence:
            for ext in external_texts:
                partial = find_partial_phrase_match(orig, ext["text"])
                if partial:
                    phrase, sim = partial
                    similarity = round(sim, 3)
                    plagiarism_data_for_db.append({
                        "matched_text": phrase,
                        "similarity": similarity,
                        "source_type": ext["type"],
                        "source_title": ext["title"],
                        "source_url": ext["source_url"],
                    })
                    if sim > highest_similarity:
                        highest_similarity = sim
                    all_matched_titles.add(ext["title"])
                    break

    # 10. Build report_doc and insert into Mongo
    highest_pct = round(highest_similarity * 100, 1)
    flagged = highest_pct > 70
    time_spent = "00:00"

    report_doc = {
        "user_id": token_payload.get("id"),
        "name": title,
        "content": raw_text,
        "date": datetime.utcnow(),
        "similarity": highest_pct,
        "sources": list(all_matched_titles),
        "word_count": len(raw_text.split()),
        "time_spent": time_spent,
        "flagged": flagged,
        "plagiarism_data": plagiarism_data_for_db,
    }

    insert_result = await reports_collection.insert_one(report_doc)
    new_id_str = str(insert_result.inserted_id)

    # 11. Return ReportDetail
    return ReportDetail(
        id=new_id_str,
        name=title,
        content=raw_text,
        plagiarism_data=plagiarism_data_for_db
    )
