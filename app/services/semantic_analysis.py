import numpy as np
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any
from motor.motor_asyncio import AsyncIOMotorClient

# Load the Sentence-Transformer model globally to avoid repeated loading
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def get_embedding_model():
    return embedding_model

def embed_text(text: str) -> list[float]:
    if not text.strip():
        return [0.0] * embedding_model.get_sentence_embedding_dimension()
    return embedding_model.encode([text])[0].tolist()

def cosine_similarity(a: List[float], b: List[float]) -> float:
    a, b = np.array(a), np.array(b)
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))

async def save_source(db: AsyncIOMotorClient, source: dict):
    source["embedding"] = embed_text(source["text"])
    await db["datas"].insert_one(source)

async def query_similar(db: AsyncIOMotorClient, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    query_emb = embed_text(text)
    
    datas_collection = db["datas"]
    docs_cursor = datas_collection.find({"embedding": {"$exists": True}}, {"_id": 0})
    docs = await docs_cursor.to_list(None)
    
    scored = []
    for d in docs:
        if "embedding" in d and d["embedding"]:
            sim = cosine_similarity(query_emb, d["embedding"])
            scored.append({
                "text": d["text"],
                "similarity": round(sim, 3),
                "title": d.get("title", ""),
                "source_url": d.get("source_url", ""),
                "type": d.get("type", "other")
            })
    
    return sorted(scored, key=lambda x: x["similarity"], reverse=True)[:top_k]