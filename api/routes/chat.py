from flask import Blueprint, jsonify, request

from db import DatabaseConfigError
from rag.llm import LLMError, ask_llm
from rag.vector_store import get_recent_chunks, has_documents, search_chunks
from routes.helpers import current_user_id, login_required

chat_bp = Blueprint("chat", __name__)

SUMMARY_TERMS = {
    "abstract",
    "brief",
    "overview",
    "summarise",
    "summarize",
    "summary",
}


def json_error(message, status=400):
    return jsonify({"error": message}), status


def is_summary_request(message):
    lowered = (message or "").lower()
    return any(term in lowered for term in SUMMARY_TERMS)


def format_page_range(source):
    start = source.get("page_start")
    end = source.get("page_end")
    if not start:
        return ""
    if not end or start == end:
        return f"p. {start}"
    return f"pp. {start}-{end}"


def format_context(sources):
    blocks = []
    for index, source in enumerate(sources, start=1):
        page_range = format_page_range(source)
        citation = f"{source['filename']} {page_range}".strip()
        blocks.append(f"[{index}] {citation}\n{source['text']}")
    return "\n\n".join(blocks)


def serialize_sources(sources):
    seen = set()
    serialized = []
    for source in sources:
        key = (source["filename"], source.get("page_start"), source.get("page_end"))
        if key in seen:
            continue
        seen.add(key)
        serialized.append(
            {
                "filename": source["filename"],
                "page": format_page_range(source),
                "score": source.get("score"),
            }
        )
    return serialized


def answer_from_files(message, sources):
    context = format_context(sources)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a careful RAG assistant. Answer using only the provided "
                "PDF context. If the context is insufficient, say that the answer "
                "is not available in the uploaded files. Keep the answer clear and "
                "include brief source references like [1] when useful."
            ),
        },
        {
            "role": "user",
            "content": f"PDF context:\n{context}\n\nQuestion: {message}",
        },
    ]
    return ask_llm(messages)


def answer_without_files(message):
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant. The answer is not coming from the "
                "user's uploaded PDFs, so answer normally and do not invent file citations."
            ),
        },
        {"role": "user", "content": message},
    ]
    return ask_llm(messages, temperature=0.35)


@chat_bp.route("/api/chat", methods=["POST"])
@chat_bp.route("/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    allow_llm = bool(data.get("allow_llm"))

    if not message:
        return json_error("Ask a question first.")

    user_id = current_user_id()

    try:
        sources = search_chunks(user_id, message)
        if not sources and is_summary_request(message):
            sources = get_recent_chunks(user_id)

        if sources:
            answer = answer_from_files(message, sources)
            return jsonify(
                {
                    "found": True,
                    "answer": answer,
                    "sources": serialize_sources(sources),
                }
            )

        if not allow_llm:
            if has_documents(user_id):
                prompt = (
                    "I couldn't find an answer in your uploaded files. "
                    "Do you want me to answer using the AI model instead?"
                )
            else:
                prompt = (
                    "You have not uploaded any PDFs yet. Do you want me to answer "
                    "using the AI model instead?"
                )
            return jsonify({"found": False, "needs_confirmation": True, "message": prompt})

        answer = answer_without_files(message)
        return jsonify({"found": False, "answer": answer, "sources": []})
    except DatabaseConfigError as error:
        return json_error(str(error), 500)
    except LLMError as error:
        return json_error(str(error), 502)