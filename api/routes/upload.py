from datetime import datetime, timezone

import fitz
from bson import ObjectId
from flask import Blueprint, jsonify, request
from werkzeug.utils import secure_filename

from db import DatabaseConfigError, ensure_indexes, get_db
from rag.vector_store import store_chunks
from routes.helpers import current_user_id, login_required

upload_bp = Blueprint("upload", __name__)

ALLOWED_EXTENSIONS = {".pdf"}


def json_error(message, status=400):
    return jsonify({"error": message}), status


def is_pdf(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "pdf"


def extract_pages(pdf_bytes):
    pages = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            if text:
                pages.append({"page": index, "text": text})
        return pages, document.page_count


def chunk_pages(pages, max_words=850, overlap=120):
    words = []
    for page in pages:
        for word in page["text"].split():
            words.append((word, page["page"]))

    if not words:
        return []

    chunks = []
    step = max_words - overlap
    for start in range(0, len(words), step):
        window = words[start : start + max_words]
        if not window:
            break

        text = " ".join(word for word, _page in window).strip()
        page_numbers = [page for _word, page in window]
        chunks.append(
            {
                "text": text,
                "page_start": min(page_numbers),
                "page_end": max(page_numbers),
            }
        )

        if start + max_words >= len(words):
            break

    return chunks


def serialize_document(document):
    return {
        "id": str(document["_id"]),
        "filename": document["filename"],
        "pages": document.get("pages", 0),
        "chunks": document.get("chunks", 0),
        "created_at": document.get("created_at").isoformat()
        if document.get("created_at")
        else None,
    }


@upload_bp.route("/api/upload", methods=["POST"])
@upload_bp.route("/upload", methods=["POST"])
@login_required
def upload_pdf():
    file = request.files.get("file")
    if not file or not file.filename:
        return json_error("Choose a PDF first.")

    if not is_pdf(file.filename):
        return json_error("Only PDF files are supported.")

    filename = secure_filename(file.filename)
    pdf_bytes = file.read()
    if not pdf_bytes:
        return json_error("The uploaded PDF is empty.")

    try:
        pages, page_count = extract_pages(pdf_bytes)
    except Exception:
        return json_error("Could not read this PDF. Try another file.")

    chunks = chunk_pages(pages)
    if not chunks:
        return json_error("No readable text was found in this PDF.")

    user_id = current_user_id()
    now = datetime.now(timezone.utc)

    try:
        ensure_indexes()
        db = get_db()
        document_result = db.documents.insert_one(
            {
                "user_id": user_id,
                "filename": filename,
                "pages": page_count,
                "chunks": len(chunks),
                "created_at": now,
            }
        )
        store_chunks(user_id, document_result.inserted_id, filename, chunks, now)
    except DatabaseConfigError as error:
        return json_error(str(error), 500)
    except Exception as error:
        return json_error(f"Upload failed: {error}", 500)

    return jsonify(
        {
            "message": "PDF uploaded and indexed.",
            "document": {
                "id": str(document_result.inserted_id),
                "filename": filename,
                "pages": page_count,
                "chunks": len(chunks),
                "created_at": now.isoformat(),
            },
        }
    )


@upload_bp.route("/api/documents", methods=["GET"])
@login_required
def list_documents():
    try:
        ensure_indexes()
        documents = list(
            get_db()
            .documents.find({"user_id": current_user_id()})
            .sort("created_at", -1)
        )
    except DatabaseConfigError as error:
        return json_error(str(error), 500)

    return jsonify({"documents": [serialize_document(document) for document in documents]})


@upload_bp.route("/api/documents/<document_id>", methods=["DELETE"])
@login_required
def delete_document(document_id):
    try:
        object_id = ObjectId(document_id)
    except Exception:
        return json_error("Invalid document id.")

    try:
        ensure_indexes()
        db = get_db()
        document = db.documents.find_one(
            {"_id": object_id, "user_id": current_user_id()}
        )
        if not document:
            return json_error("Document not found.", 404)

        db.chunks.delete_many({"document_id": object_id, "user_id": current_user_id()})
        db.documents.delete_one({"_id": object_id, "user_id": current_user_id()})
    except DatabaseConfigError as error:
        return json_error(str(error), 500)

    return jsonify({"message": "Document deleted."})
