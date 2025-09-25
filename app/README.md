# Plagiarism Checker (FastAPI)

## Overview
This service provides a `/plagiarism/check` endpoint that accepts a file upload (TXT, PDF, DOCX) or raw text, splits it into sentences, and compares each sentence against News API and CORE API sources using:
1. Exact substring match
2. SequenceMatcher + TF–IDF cosine similarity
3. 5-word sliding‐window fallback

Matches are returned sentence‐by‐sentence in JSON format. A timestamped JSON file is also saved in the same folder as `main.py`.

## Folder Structure
project_root/
├── app/
│ ├── main.py
│ ├── config.py
│ ├── routers/
│ │ ├── health.py
│ │ └── plagiarism.py
│ ├── services/
│ │ ├── news_api.py
│ │ └── core_api.py
│ ├── models/
│ │ └── schemas.py
│ └── utils/
│ ├── text_utils.py
│ └── file_utils.py
├── requirements.txt
└── README.md


## Setup & Run
1. Install dependencies:
   ```bash
   pip install -r requirements.txt





With this structure:

1. **No logic has changed**—every function and endpoint is identical to your working version.  
2. Routes live under `app/routers`.  
3. External‐API calls are isolated in `app/services`.  
4. Schemas are in `app/models/schemas.py`.  
5. Text‐processing and file‐processing helpers are in `app/utils`.  
6. Configuration (API keys, thresholds, URLs) is centralized in `app/config.py`.  

You can now run:
```bash
uvicorn app.main:app --reload

--by Awais
# FastAPI Plagiarism Detector API

A sophisticated plagiarism detection system built with FastAPI that uses both lexical analysis and semantic analysis (RAG) for comprehensive text similarity detection.

## Features

- **Dual Analysis Modes**:
  - **Students**: Lexical analysis only (exact matches, phrase matching)
  - **Teachers**: Full RAG implementation with semantic analysis (60% semantic + lexical)
- **Advanced Text Processing**: NLTK-based normalization, winnowing fingerprinting, LCS matching
- **User Authentication**: JWT-based auth with role-based access
- **File Support**: PDF, DOCX, TXT uploads
- **Batch Processing**: Teachers can upload and compare multiple files
- **Inter-Document Analysis**: Compare submitted documents against each other

## Project Structure

```
fastapi-plagiarism-detector-api/
├── app/
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py              # Configuration and environment variables
│   ├── dependencies/
│   │   └── auth.py            # Authentication dependencies
│   ├── models/
│   │   └── schemas.py         # Pydantic models
│   ├── routers/
│   │   ├── auth.py           # Authentication endpoints
│   │   ├── health.py         # Health check endpoints
│   │   └── plagiarism.py     # Main plagiarism detection endpoints
│   ├── services/
│   │   └── semantic_analysis.py  # RAG/embedding services
│   └── utils/
│       ├── file_utils.py     # File processing utilities
│       └── text_utils.py     # Advanced text analysis utilities
└── requirements.txt
```

## Installation & Setup

### 1. Prerequisites

- Python 3.8+
- MongoDB database
- Git

### 2. Clone Repository

```bash
git clone <your-repo-url>
cd fastapi-plagiarism-detector-api
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**
```
fastapi
uvicorn[standard]
motor
python-jose[cryptography]
python-multipart
sentence-transformers
nltk
rapidfuzz
pdfminer.six
python-docx
scikit-learn
numpy
python-dotenv
```

### 4. Environment Setup

Create a `.env` file in the root directory:

```env
# Database
MONGODB_URI=mongodb://localhost:27017/plagiarism_detector

# Security
SECRET_KEY=your_super_secret_key_here_change_in_production

# Optional API Keys (currently not used)
GUARDIAN_API_KEY=""
CORE_API_KEY=""
```

### 5. MongoDB Setup

Ensure MongoDB is running and create the required collections:
- `users` - User authentication data
- `reports` - Plagiarism check reports
- `datas` - Document database for plagiarism checking

### 6. Run the Application

```bash
uvicorn app.main:app --reload
```

The API will be available at: `http://127.0.0.1:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: `http://127.0.0.1:8000/docs`
- **ReDoc**: `http://127.0.0.1:8000/redoc`

## API Endpoints

### Authentication

#### Register User
```http
POST /auth/register
Content-Type: application/x-www-form-urlencoded

email=user@example.com&password=securepass&is_teacher=false
```

**Response:**
```json
{
  "message": "User registered successfully"
}
```

#### Login
```http
POST /auth/login
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=securepass
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

### Health Check

#### System Status
```http
GET /health/health
```

**Response:**
```json
{
  "status": "ok",
  "guardian_api_key_present": false,
  "core_api_key_present": false,
  "mongodb_URI_present": true
}
```

### Plagiarism Detection

#### Student Plagiarism Check (Lexical Only)
```http
POST /api/plagiarism/check
Authorization: Bearer <your_jwt_token>
Content-Type: multipart/form-data

file=@document.pdf  # OR
text="Your text content here"
```

**Response:**
```json
{
  "id": "64f1234567890abcdef12345",
  "name": "document.pdf",
  "content": "Full text content...",
  "plagiarism_data": [
    {
      "matched_text": "This is a plagiarized sentence",
      "similarity": 0.95,
      "source_type": "academic",
      "source_title": "Source Document Title",
      "source_url": "http://example.com/source"
    }
  ]
}
```

#### Teacher Batch Analysis (RAG + Semantic)
```http
POST /api/plagiarism/check-teacher-files
Authorization: Bearer <teacher_jwt_token>
Content-Type: multipart/form-data

files=@student1.pdf&files=@student2.pdf&files=@student3.pdf
```

**Response:**
```json
{
  "hybrid_reports": [
    {
      "id": "64f1234567890abcdef12345",
      "name": "student1.pdf",
      "content": "Student text...",
      "plagiarism_data": [...]
    }
  ],
  "batch_comparison": [
    {
      "doc_a": "student1.pdf",
      "doc_b": "student2.pdf",
      "similarity": 0.87
    }
  ]
}
```

#### Add Documents to Database (Teachers Only)
```http
POST /api/plagiarism/add-documents
Authorization: Bearer <teacher_jwt_token>
Content-Type: multipart/form-data

files=@reference1.pdf&files=@reference2.pdf
```

**Response:**
```json
{
  "message": "Successfully added 2 documents.",
  "filenames": ["reference1.pdf", "reference2.pdf"]
}
```

## User Roles & Permissions

### Students
- Can register and login
- Single file upload only
- Lexical analysis only (no semantic embeddings)
- Cannot add documents to database
- Access to: `/api/plagiarism/check`

### Teachers
- Can register with `is_teacher=true`
- Multiple file uploads (batch processing)
- Full RAG implementation (semantic + lexical)
- Can add reference documents to database
- Inter-document similarity comparison
- Access to: `/api/plagiarism/check-teacher-files`, `/api/plagiarism/add-documents`

## Testing the API

### Using cURL

1. **Register a student:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=student@test.com&password=testpass&is_teacher=false"
```

2. **Register a teacher:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/register" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "email=teacher@test.com&password=testpass&is_teacher=true"
```

3. **Login:**
```bash
curl -X POST "http://127.0.0.1:8000/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=student@test.com&password=testpass"
```

4. **Check plagiarism (save the token from login):**
```bash
curl -X POST "http://127.0.0.1:8000/api/plagiarism/check" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F "text=This is some sample text to check for plagiarism."
```

### Using Python requests

```python
import requests

# Register and login
response = requests.post("http://127.0.0.1:8000/auth/login", 
                        data={"username": "student@test.com", "password": "testpass"})
token = response.json()["access_token"]

# Check plagiarism
headers = {"Authorization": f"Bearer {token}"}
files = {"file": open("sample.pdf", "rb")}
response = requests.post("http://127.0.0.1:8000/api/plagiarism/check", 
                        headers=headers, files=files)
print(response.json())
```

## Advanced Features

### Text Analysis Algorithms

1. **Winnowing Fingerprinting**: Detects exact and near-exact matches
2. **Longest Common Substring (LCS)**: Catches long contiguous overlaps
3. **Levenshtein Distance**: Handles paraphrased content
4. **Jaccard/Containment**: Measures phrase-level similarity
5. **Semantic Embeddings**: Uses sentence-transformers for semantic similarity

### File Processing

- **PDF**: Advanced text extraction with pdfminer
- **DOCX**: Full document parsing including paragraphs
- **TXT**: UTF-8 with error handling

### Performance Optimizations

- Semantic search only for top-K candidates
- Efficient MongoDB text indexing
- Batch processing with multiprocessing support
- Memory-efficient streaming for large files

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all paths use `app.` prefix
2. **NLTK Data**: Downloads automatically on first run
3. **MongoDB Connection**: Check MONGODB_URI in .env
4. **JWT Errors**: Verify SECRET_KEY is set
5. **File Upload**: Ensure proper multipart/form-data headers

### Logs

Check uvicorn logs for detailed error information:
```bash
uvicorn app.main:app --reload --log-level debug
```

## Development Notes

- **Lexical vs Semantic**: Students get lexical-only analysis, teachers get both
- **RAG Implementation**: 60% of functionality uses semantic analysis
- **Security**: Teachers verified before accessing advanced features
- **Scalability**: Designed for academic institution use

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

[Add your license information here]
