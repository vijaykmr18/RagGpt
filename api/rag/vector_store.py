import hashlib
import math
import os
import re

from db import ensure_indexes, get_db

TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_\-']*")
EMBEDDING_DIM = int(os.getenv("RAG_EMBEDDING_DIM", "384"))
MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.18"))

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "you",
    "your",
}


def tokenize(text):
    return [
        token.lower().strip("'")
        for token in TOKEN_RE.findall(text or "")
        if len(token) > 2 and token.lower() not in STOP_WORDS
    ]


def stable_bucket(token):
    digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % EMBEDDING_DIM


def embed_text(text):
    tokens = tokenize(text)
    vector = [0.0] * EMBEDDING_DIM

    for token in tokens:
        vector[stable_bucket(token)] += 1.0

    for left, right in zip(tokens, tokens[1:]):
        vector[stable_bucket(f"{left} {right}")] += 0.45

    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector

    return [round(value / norm, 6) for value in vector]


def cosine_similarity(left, right):
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def coverage_score(query_terms, text):
    if not query_terms:
        return 0.0
    text_terms = set(tokenize(text))
    if not text_terms:
        return 0.0
    return len(query_terms & text_terms) / len(query_terms)


def store_chunks(user_id, document_id, filename, chunks, created_at):
    ensure_indexes()
    documents = []

    for index, chunk in enumerate(chunks):
        text = chunk["text"]
        documents.append(
            {
                "user_id": user_id,
                "document_id": document_id,
                "filename": filename,
                "chunk_index": index,
                "text": text,
                "page_start": chunk.get("page_start"),
                "page_end": chunk.get("page_end"),
                "vector": embed_text(text),
                "created_at": created_at,
            }
        )

    if documents:
        get_db().chunks.insert_many(documents)

    return len(documents)


def search_chunks(user_id, query, top_k=5):
    ensure_indexes()
    query_vector = embed_text(query)
    query_terms = set(tokenize(query))
    candidates = []

    cursor = get_db().chunks.find(
        {"user_id": user_id},
        {
            "filename": 1,
            "text": 1,
            "page_start": 1,
            "page_end": 1,
            "vector": 1,
            "chunk_index": 1,
        },
    )

    for chunk in cursor:
        vector_score = cosine_similarity(query_vector, chunk.get("vector", []))
        overlap_score = coverage_score(query_terms, chunk.get("text", ""))
        score = (vector_score * 0.72) + (overlap_score * 0.28)

        if score >= MIN_SCORE:
            candidates.append(
                {
                    "text": chunk["text"],
                    "filename": chunk["filename"],
                    "page_start": chunk.get("page_start"),
                    "page_end": chunk.get("page_end"),
                    "score": round(score, 4),
                }
            )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:top_k]


def has_documents(user_id):
    ensure_indexes()
    return get_db().documents.count_documents({"user_id": user_id}, limit=1) > 0


def get_recent_chunks(user_id, top_k=6):
    ensure_indexes()
    latest_document = get_db().documents.find_one(
        {"user_id": user_id},
        sort=[("created_at", -1)],
    )
    if not latest_document:
        return []

    chunks = list(
        get_db()
        .chunks.find(
            {"user_id": user_id, "document_id": latest_document["_id"]},
            {
                "filename": 1,
                "text": 1,
                "page_start": 1,
                "page_end": 1,
                "chunk_index": 1,
            },
        )
        .sort("chunk_index", 1)
        .limit(top_k)
    )

    return [
        {
            "text": chunk["text"],
            "filename": chunk["filename"],
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
            "score": 1.0,
        }
        for chunk in chunks
    ]
