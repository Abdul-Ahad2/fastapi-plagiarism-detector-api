from pydantic import BaseModel,Field
from typing import List, Optional
from datetime import datetime

# ───── Existing plagiarism‐response models ─────

# A simple model for API messages
class Message(BaseModel):
    message: str

# Authentication and User models
class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    id: str = Field(alias="_id")
    email: str
    is_active: bool = True
    is_teacher: Optional[bool] = False

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            # This is optional, but good for handling BSON ObjectId
            datetime: lambda v: v.isoformat() if v else None
        }


class MatchDetail(BaseModel):
    matched_text: str
    similarity: float
    source_type: str    # "news" or "academic"
    source_title: str
    source_url: str


class SentenceResult(BaseModel):
    original_sentence: str
    normalized_sentence: str
    match_type: str     # "full_sentence", "partial_phrase", "no_match"
    matches: List[MatchDetail]


class PlagiarismResponse(BaseModel):
    checked_sentences: int
    checked_sources: int
    results: List[SentenceResult]


# ───── Models for “Reports” endpoints ─────

class ReportSummary(BaseModel):
    id: str                # MongoDB’s ObjectId as string
    name: str
    date: datetime
    similarity: float       # highest sentence‐level similarity (0–100)
    sources: List[str]      # unique list of source titles used
    word_count: int
    time_spent: str         # e.g. "00:00"
    flagged: bool           # true if similarity > 70%


class ReportDetail(BaseModel):
    id: str
    name: str
    content: str
    plagiarism_data: List[MatchDetail]
    rag_summary: Optional[str] = None

class SourceData(BaseModel):
    id: str          # MongoDB ObjectId as string
    title: str
    text: str
    source_url: str
    type: str 
    embedding: Optional[List[float]] = None