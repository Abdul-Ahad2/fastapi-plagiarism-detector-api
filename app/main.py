import logging
from fastapi import FastAPI
from app.routers.health import router as health_router
from app.routers.plagiarism import router as plagiarism_router
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://plagiarism-detection-frontend.vercel.app", "*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(plagiarism_router)
