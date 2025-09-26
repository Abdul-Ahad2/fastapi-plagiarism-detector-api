import re
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Depends
from motor.motor_asyncio import AsyncIOMotorClient
import numpy as np
import uuid

from app.models.schemas import MatchDetail, ReportDetail, User
from app.services.semantic_analysis import (
    embed_text,
    cosine_similarity,
    save_source
)
from app.utils.file_utils import extract_text_from_file, allowed_file
from app.utils.text_utils import (
    get_meaningful_sentences,
    extract_keywords,
    find_exact_matches,
    find_partial_phrase_match,
)
from app.dependencies.auth import get_mongo_client, get_current_user


router = APIRouter()

@router.post("/plagiarism/check", response_model=ReportDetail)
async def check_plagiarism(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client),
    current_user: User = Depends(get_current_user),
):
    """
    Student plagiarism check - LEXICAL ONLY (no semantic analysis)
    Students can only upload single files and get lexical analysis
    """
    start = datetime.utcnow()
    db = mongo_client["plagiarism_detector"]
    reports_collection = db["reports"]
    data_collection = db["datas"]

    # Input validation
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

    # Get sentences for analysis
    sentences = get_meaningful_sentences(raw_text)
    if not sentences:
        report_doc = {
            "user_id": current_user.id,
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
        insert_result = await reports_collection.insert_one(report_doc)
        return ReportDetail(
            id=str(insert_result.inserted_id),
            name=title,
            content=raw_text,
            plagiarism_data=[]
        )
    
    # Extract keywords for database search
    keywords = extract_keywords(raw_text, max_keywords=5)
    query_text = " ".join(keywords) if keywords else raw_text[:100]

    # Search database using text search (LEXICAL ONLY - no embeddings)
    try:
        cursor = data_collection.find(
            {"$text": {"$search": query_text}},
            {"score": {"$meta": "textScore"}, "title": 1, "text": 1, "source_url": 1, "type": 1},
        ).sort([("score", {"$meta": "textScore"})]).limit(200)
        external_texts = await cursor.to_list(length=200)
    except Exception:
        # Fallback to regex search
        tokens = keywords or re.findall(r"\w+", query_text)
        if tokens:
            regex = "|".join(re.escape(t) for t in tokens)
            cursor = data_collection.find(
                {"$or": [
                    {"title": {"$regex": regex, "$options": "i"}},
                    {"text": {"$regex": regex, "$options": "i"}},
                ]},
                {"title": 1, "text": 1, "source_url": 1, "type": 1}
            ).limit(200)
            external_texts = await cursor.to_list(length=200)
        else:
            external_texts = []
    
    if not external_texts:
        report_doc = {
            "user_id": current_user.id,
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
        insert_result = await reports_collection.insert_one(report_doc)
        return ReportDetail(
            id=str(insert_result.inserted_id),
            name=title,
            content=raw_text,
            plagiarism_data=[]
        )

    # LEXICAL ANALYSIS ONLY (no semantic embeddings for students)
    plagiarism_data_for_db: List[dict] = []
    highest_similarity = 0.0
    all_matched_titles = set()

    for orig_sentence in sentences:
        matched = False
        
        # First try exact matches
        for ext in external_texts:
            exact_sim = find_exact_matches(orig_sentence, ext["text"])
            if exact_sim is not None:
                plagiarism_data_for_db.append({
                    "matched_text": orig_sentence,
                    "similarity": exact_sim,
                    "source_type": ext.get("type", "other"),
                    "source_title": ext.get("title", "Unknown"),
                    "source_url": ext.get("source_url", ""),
                })
                matched = True
                highest_similarity = max(highest_similarity, exact_sim)
                all_matched_titles.add(ext.get("title"))
                break

        # If no exact match, try partial phrase matching
        if not matched:
            for ext in external_texts:
                partial_result = find_partial_phrase_match(orig_sentence, ext["text"])
                if partial_result:
                    phrase, sim = partial_result
                    plagiarism_data_for_db.append({
                        "matched_text": phrase,
                        "similarity": sim,
                        "source_type": ext.get("type", "other"),
                        "source_title": ext.get("title", "Unknown"),
                        "source_url": ext.get("source_url", ""),
                    })
                    highest_similarity = max(highest_similarity, sim)
                    all_matched_titles.add(ext.get("title"))
                    break

    # Calculate processing time
    elapsed = datetime.utcnow() - start
    total_sec = int(elapsed.total_seconds())
    mins, secs = divmod(total_sec, 60)
    hours, mins = divmod(mins, 60)
    time_spent = f"{hours:d}:{mins:02d}:{secs:02d}" if hours else f"{mins:02d}:{secs:02d}"

    highest_pct = round(highest_similarity * 100, 1)
    flagged = highest_pct > 70

    report_doc = {
        "user_id": current_user.id,
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
    insert_res = await reports_collection.insert_one(report_doc)
    
    return ReportDetail(
        id=str(insert_res.inserted_id),
        name=title,
        content=raw_text,
        plagiarism_data=plagiarism_data_for_db
    )

@router.post("/plagiarism/check-teacher-files")
async def check_teacher_files(
    files: List[UploadFile] = File(...),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client),
    current_user: User = Depends(get_current_user),
):
    """
    Teacher plagiarism check - INCLUDES SEMANTIC ANALYSIS (RAG 60%)
    Teachers can upload multiple files and get both lexical + semantic analysis
    """
    # Verify user is a teacher
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can use batch file processing")
    
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    db = mongo_client.get_default_database()
    reports_collection = db["reports"]
    data_collection = db["datas"]

    # Process all uploaded files
    submitted_docs = []
    for file in files:
        if not allowed_file(file.filename):
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file.filename}")
        content = await file.read()
        text = extract_text_from_file(content, file.filename)
        if not text.strip():
            continue

        submitted_docs.append({
            "filename": file.filename,
            "content": text,
        })

    if not submitted_docs:
        raise HTTPException(status_code=400, detail="No readable text found in uploaded files.")

    reports = []
    for doc in submitted_docs:
        start_time = datetime.utcnow()
        title = doc["filename"]
        student_text = doc["content"]
        
        # SEMANTIC ANALYSIS (RAG) - Only for teachers
        student_embedding = embed_text(student_text)

        # Get all documents with embeddings from database
        db_docs_cursor = data_collection.find({}, {
            "_id": 0, "title": 1, "text": 1, "source_url": 1, "type": 1, "embedding": 1
        })
        db_docs = await db_docs_cursor.to_list(None)

        # Calculate semantic similarities
        semantic_scores = []
        for db_doc in db_docs:
            if db_doc.get("embedding"):
                db_embedding = np.array(db_doc["embedding"])
                sim = cosine_similarity(student_embedding, db_embedding)
                semantic_scores.append({"doc": db_doc, "similarity": sim})

        # Sort by similarity and take top candidates
        semantic_scores.sort(key=lambda x: x["similarity"], reverse=True)
        top_k_candidates = semantic_scores[:20]  # Top 20 most similar documents

        # Now do detailed lexical analysis on the most promising candidates
        all_matched_titles = set()
        all_matches: List[MatchDetail] = []
        sentences = get_meaningful_sentences(student_text)

        for orig_sentence in sentences:
            found_match = False
            
            # Check against top semantic candidates first
            for candidate in top_k_candidates:
                source_text = candidate["doc"]["text"]
                source_meta = candidate["doc"]

                # Try exact match first
                exact_match_sim = find_exact_matches(orig_sentence, source_text)
                if exact_match_sim is not None and exact_match_sim > 0.6:
                    all_matches.append(MatchDetail(
                        matched_text=orig_sentence,
                        similarity=exact_match_sim,
                        source_type=source_meta.get('type', 'other'),
                        source_title=source_meta.get('title', 'Unknown'),
                        source_url=source_meta.get('source_url', '')
                    ))
                    all_matched_titles.add(source_meta.get('title'))
                    found_match = True
                    break
                
                # Try partial phrase match
                partial_match = find_partial_phrase_match(orig_sentence, source_text)
                if partial_match:
                    phrase, sim = partial_match
                    if sim > 0.6:
                        all_matches.append(MatchDetail(
                            matched_text=phrase,
                            similarity=sim,
                            source_type=source_meta.get('type', 'other'),
                            source_title=source_meta.get('title', 'Unknown'),
                            source_url=source_meta.get('source_url', '')
                        ))
                        all_matched_titles.add(source_meta.get('title'))
                        found_match = True
                        break

        # Calculate processing time
        elapsed_time = datetime.utcnow() - start_time
        total_seconds = int(elapsed_time.total_seconds())
        time_spent = f"{total_seconds // 3600:d}:{(total_seconds % 3600) // 60:02d}:{total_seconds % 60:02d}"

        highest_similarity = max([m.similarity for m in all_matches], default=0.0)
        flagged = highest_similarity > 0.7

        # Store report
        report_doc = {
            "user_id": current_user.id,
            "name": title,
            "date": datetime.utcnow(),
            "similarity": round(highest_similarity * 100, 1),
            "sources": list(all_matched_titles),
            "word_count": len(student_text.split()),
            "time_spent": time_spent,
            "flagged": flagged,
            "plagiarism_data": [m.dict() for m in all_matches],
            "content": student_text
        }

        insert_res = await reports_collection.insert_one(report_doc)
        reports.append(ReportDetail(
            id=str(insert_res.inserted_id),
            name=title,
            content=student_text,
            plagiarism_data=all_matches
        ))

    # BATCH COMPARISON - Compare submitted documents against each other
    submitted_embeddings = [embed_text(d["content"]) for d in submitted_docs]
    n = len(submitted_embeddings)
    pairwise_results = []

    for i in range(n):
        for j in range(i + 1, n):
            sim = cosine_similarity(submitted_embeddings[i], submitted_embeddings[j])
            pairwise_results.append({
                "doc_a": submitted_docs[i]["filename"],
                "doc_b": submitted_docs[j]["filename"],
                "similarity": round(sim, 3)
            })

    return {
        "hybrid_reports": [r.dict() for r in reports],
        "batch_comparison": pairwise_results
    }

@router.post("/plagiarism/add-documents")
async def add_documents_to_database(
    files: List[UploadFile] = File(...),
    mongo_client: AsyncIOMotorClient = Depends(get_mongo_client),
    current_user: User = Depends(get_current_user)
):
    """
    Add documents to the database for plagiarism checking
    Only teachers can add documents to the database
    """
    # Verify user is a teacher
    if not current_user.is_teacher:
        raise HTTPException(status_code=403, detail="Only teachers can add documents to the database")
        
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    db = mongo_client["plagiarism_detector"]
    documents_added = []

    for file in files:
        if not allowed_file(file.filename):
            raise HTTPException(status_code=400, detail=f"Invalid file type: {file.filename}")

        content = await file.read()
        text = extract_text_from_file(content, file.filename)

        if not text.strip():
            continue

        doc = {
            "_id": str(uuid.uuid4()),
            "title": file.filename,
            "text": text,
            "source_url": "",
            "type": "teacher_upload"
        }

        # This will automatically add embeddings via the save_source function
        await save_source(db, doc)
        documents_added.append(file.filename)

    if not documents_added:
        raise HTTPException(status_code=400, detail="No readable text found in uploaded files.")

    return {
        "message": f"Successfully added {len(documents_added)} documents.", 
        "filenames": documents_added
    }