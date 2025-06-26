import asyncio
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from motor.motor_asyncio import AsyncIOMotorClient
from jose import jwt, JWTError

from app.models.schemas import MatchDetail, ReportDetail
from app.services.core_api import fetch_core_articles
from app.services.guardian_api import fetch_guardian_all_pages
from app.utils.file_utils import extract_text_from_file, allowed_file
from app.utils.text_utils import (
    normalize_text,
    get_meaningful_sentences,
    extract_keywords,
    find_exact_matches,
    find_partial_phrase_match,
    extract_full_text_from_pdf_url,
)
from app.config import MIN_SENTENCE_LENGTH, MONGODB_URI

router = APIRouter()

# ───── JWT setup ─────
SECRET_KEY = "your_nextauth_secret"
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
    start = datetime.utcnow()
    db = mongo_client.get_default_database()
    reports_collection = db["reports"]

    # 1. Extract raw text
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
        empty_doc = {
            "user_id": token_payload.get("sub"),
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

    # 3. Extract keywords for query
    keywords = extract_keywords(raw_text, max_keywords=5)
    query = " ".join(keywords) if keywords else raw_text[:100]

    # 4. Fetch CORE.ac and Guardian in parallel
    core_task     = fetch_core_articles(query)
    guardian_task = fetch_guardian_all_pages(query, max_pages=3)
    core_works, guardian_articles = await asyncio.gather(core_task, guardian_task)

    external_texts = []

    # 5. Process CORE API results
    for work in core_works:
        content = work.get("text", "")
        if not content.strip() and work.get("download_url"):
            content = await extract_full_text_from_pdf_url(work["download_url"])
        if not content.strip() and work.get("abstract"):
            content = work["abstract"]
        if content.strip():
            external_texts.append({
                "text":       content,
                "title":      work.get("title", "Unknown"),
                "source_url": f"https://core.ac.uk/works/{work.get('id','')}",
                "type":       "academic",
            })

    # 6. Process Guardian results
    for art in guardian_articles:
        txt = art.get("text", "").strip()
        if txt:
            external_texts.append({
                "text":       txt,
                "title":      art.get("title", ""),
                "source_url": art.get("url", ""),
                "type":       "news",
            })

    # 7. If no external_texts → empty report
    if not external_texts:
        empty_doc = {
            "user_id": token_payload.get("sub"),
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

    # 8. Normalize texts for matching
    for ext in external_texts:
        ext["normalized_text"] = normalize_text(ext["text"])

    # 9. Perform matching
    plagiarism_data_for_db: List[dict] = []
    highest_similarity = 0.0
    all_matched_titles = set()

    for orig in sentences:
        matched = False
        for ext in external_texts:
            sim = find_exact_matches(orig, ext["text"])
            if sim is not None:
                score = round(sim, 3)
                plagiarism_data_for_db.append({
                    "matched_text": orig,
                    "similarity":   score,
                    "source_type":  ext["type"],
                    "source_title": ext["title"],
                    "source_url":   ext["source_url"],
                })
                matched = True
                highest_similarity = max(highest_similarity, sim)
                all_matched_titles.add(ext["title"])
                break

        if not matched:
            for ext in external_texts:
                partial = find_partial_phrase_match(orig, ext["text"])
                if partial:
                    phrase, sim = partial
                    score = round(sim, 3)
                    plagiarism_data_for_db.append({
                        "matched_text": phrase,
                        "similarity":   score,
                        "source_type":  ext["type"],
                        "source_title": ext["title"],
                        "source_url":   ext["source_url"],
                    })
                    highest_similarity = max(highest_similarity, sim)
                    all_matched_titles.add(ext["title"])
                    break

    # 10. Compute elapsed time
    elapsed   = datetime.utcnow() - start
    total_sec = int(elapsed.total_seconds())
    mins, secs= divmod(total_sec, 60)
    hours, mins= divmod(mins, 60)
    time_spent = f"{hours:d}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"

    # 11. Persist and return
    highest_pct = round(highest_similarity * 100, 1)
    flagged     = highest_pct > 70

    report_doc = {
        "user_id":       token_payload.get("sub"),
        "name":          title,
        "date":          datetime.utcnow(),
        "similarity":    highest_pct,
        "sources":       list(all_matched_titles),
        "word_count":    len(raw_text.split()),
        "time_spent":    time_spent,
        "flagged":       flagged,
        "plagiarism_data": [
            {
                "similarity":   e["similarity"],
                "source_type":  e["source_type"],
                "source_title": e["source_title"],
                "source_url":   e["source_url"],
            }
            for e in plagiarism_data_for_db
        ],
    }
    insert_res = await reports_collection.insert_one(report_doc)
    return ReportDetail(
        id=str(insert_res.inserted_id),
        name=title,
        content=raw_text,
        plagiarism_data=plagiarism_data_for_db
    )
