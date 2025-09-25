from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

# Import the routers for your API endpoints
from app.routers.plagiarism import router as plagiarism_router
from app.routers.auth import router as auth_router  # Fixed import path
from app.routers.health import router as health_router

# Check if the required environment variables are set
if not os.getenv("MONGODB_URI"):
    raise ValueError("The MONGODB_URI environment variable is not set. Please set it to connect to your MongoDB database.")
if not os.getenv("SECRET_KEY"):
    raise ValueError("The SECRET_KEY environment variable is not set. It's required for secure authentication.")

# Create the FastAPI application instance
app = FastAPI(
    title="Plagiarism Detector API",
    description="An API for detecting plagiarism and semantic similarity.",
    version="1.0.0",
    redoc_url="/redoc",
    docs_url="/docs"
)

# Set up CORS middleware to allow requests from your frontend application
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include the routers to add their endpoints to the application
app.include_router(health_router, prefix="/health", tags=["Health"])
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(plagiarism_router, prefix="/api", tags=["Plagiarism"])

# A simple root endpoint to confirm the API is running
@app.get("/")
def read_root():
    return {"message": "Welcome to the Plagiarism Detector API!"}