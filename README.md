# RAG GPT Flask Web App

A serverless-ready Flask app for signing in, uploading PDFs, and asking questions with a RAG-first chat flow. Uploaded PDFs are parsed in memory, chunked, indexed in MongoDB, and used as context for OpenRouter chat completions.

## Features

- Signup, signin, and session-based auth
- Per-user PDF uploads for ebooks, research papers, and question papers
- MongoDB-backed document and chunk storage
- Serverless-friendly RAG retrieval without local model downloads
- OpenRouter LLM fallback after user confirmation
- ChatGPT-style dashboard with upload sidebar
- Vercel deployment config included

## Environment

Copy `.env.example` to `.env` for local development.

```env
OPENROUTER_API_KEY=your_key
OPENROUTER_MODEL=openai/gpt-4.1-mini
SECRET_KEY=your_secret
DATABASE_URL=mongodb://localhost:27017/RAGGPT
MONGO_DB_NAME=RAGGPT
CHROMA_DB_PATH=./chroma_db
```

For Vercel, add the same values in Project Settings > Environment Variables. Use MongoDB Atlas for `DATABASE_URL` when deploying.

## Local Run

```bash
python -m pip install -r requirements.txt
python api/index.py
```

Open `http://127.0.0.1:5000`.

## Deploy To Vercel

1. Push this folder to GitHub.
2. Import the GitHub repo in Vercel.
3. Add the environment variables from `.env.example`.
4. Deploy.

## Notes

Vercel functions do not provide reliable persistent disk storage, so this version stores users, PDF metadata, chunks, and retrieval vectors in MongoDB. `CHROMA_DB_PATH` is kept in the env sample for compatibility with your original config, but the deployed app does not depend on local Chroma files.
# RagGpt
