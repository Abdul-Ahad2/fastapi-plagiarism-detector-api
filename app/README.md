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
