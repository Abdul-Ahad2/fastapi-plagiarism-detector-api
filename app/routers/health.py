from fastapi import APIRouter
from config import MONGODB_URI, GUARDIAN_API_KEY, CORE_API_KEY

router = APIRouter()

@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "gaurdian_api_key_present": bool(GUARDIAN_API_KEY),
        "core_api_key_present": bool(CORE_API_KEY),
        "mongodb_URI_present": bool(MONGODB_URI),
    }
