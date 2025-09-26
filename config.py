import os
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# --- Security & Auth ---
SECRET_KEY = os.getenv("SECRET_KEY", "your_nextauth_secret_in_development")
ALGORITHM = "HS256"

# --- API Keys (optional - not currently used in implementation) ---
GUARDIAN_API_KEY = os.getenv("GUARDIAN_API_KEY", "")
CORE_API_KEY = os.getenv("CORE_API_KEY", "")

# --- Database ---
MONGODB_URI = os.getenv("MONGODB_URI")
if not MONGODB_URI:
    raise ValueError("No MONGODB_URI found in environment variables.")

# --- Plagiarism Constants ---
MIN_WORDS_PER_SENTENCE = 5
MIN_SENTENCE_LENGTH = 15
SEQUENCE_THRESHOLD = 0.75
EXACT_MATCH_SCORE = 1.0

# --- File Upload ---
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}