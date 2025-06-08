import re
from typing import List, Optional
import nltk
from nltk.tokenize import sent_tokenize, word_tokenize
from nltk.corpus import stopwords
from difflib import SequenceMatcher
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from newspaper import Article
from app.config import MIN_WORDS_PER_SENTENCE, MIN_SENTENCE_LENGTH, SEQUENCE_THRESHOLD, TFIDF_THRESHOLD, EXACT_MATCH_SCORE


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_meaningful_sentences(text: str) -> List[str]:
    sentences = sent_tokenize(text)
    filtered = []
    for s in sentences:
        words = word_tokenize(s)
        if len(words) >= MIN_WORDS_PER_SENTENCE and len(s.strip()) >= MIN_SENTENCE_LENGTH:
            filtered.append(s.strip())
    return filtered


def extract_keywords(text: str, max_keywords: int = 5) -> List[str]:
    words = word_tokenize(text.lower())
    stop_words = set(stopwords.words("english"))
    filtered = [w for w in words if w.isalpha() and w not in stop_words and len(w) > 3]
    freq = nltk.FreqDist(filtered)
    return [word for word, _ in freq.most_common(max_keywords)]


def compute_tfidf_similarity(text1: str, text2: str) -> float:
    if not text1 or not text2:
        return 0.0
    vectorizer = TfidfVectorizer(lowercase=True, token_pattern=r"\b[a-zA-Z]{2,}\b", strip_accents="unicode")
    try:
        tfidf = vectorizer.fit_transform([text1, text2])
        sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
        return float(sim)
    except Exception:
        return 0.0


def find_exact_matches(sentence: str, external_text: str) -> Optional[float]:
    normalized_sentence = normalize_text(sentence)
    normalized_external = normalize_text(external_text)
    if len(normalized_sentence) < MIN_SENTENCE_LENGTH:
        return None

    # 1) Exact‐substring check
    if normalized_sentence in normalized_external:
        return EXACT_MATCH_SCORE

    # 2) SequenceMatcher filter
    seq_sim = SequenceMatcher(None, normalized_sentence, normalized_external).ratio()
    if seq_sim >= SEQUENCE_THRESHOLD:
        # 3) TF–IDF check
        tfidf_sim = compute_tfidf_similarity(normalized_sentence, normalized_external)
        if tfidf_sim >= TFIDF_THRESHOLD:
            return tfidf_sim

    return None


def find_partial_phrase_match(sentence: str, external_text: str) -> Optional[tuple[str, float]]:
    normalized_sentence = normalize_text(sentence)
    normalized_external = normalize_text(external_text)
    words = normalized_sentence.split()
    if len(words) < 5:
        return None

    for i in range(len(words) - 4):
        phrase = " ".join(words[i : i + 5])
        if len(phrase) < MIN_SENTENCE_LENGTH:
            continue
        if phrase in normalized_external:
            sim = compute_tfidf_similarity(phrase, normalized_external)
            return phrase, sim

    return None


def extract_full_text_from_news_article(url: str) -> str:
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text or ""
    except Exception:
        return ""


async def extract_full_text_from_pdf_url(url: str) -> str:
    import httpx
    from app.utils.file_utils import extract_text_from_file
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return extract_text_from_file(resp.content, "temp.pdf")
    except Exception:
        return ""
