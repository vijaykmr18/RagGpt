import os

import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


class LLMError(RuntimeError):
    pass


def ask_llm(messages, temperature=0.2, max_tokens=900):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMError("OPENROUTER_API_KEY is not configured.")

    if isinstance(messages, str):
        messages = [{"role": "user", "content": messages}]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": os.getenv("APP_URL", "http://localhost:5000"),
        "X-Title": os.getenv("OPENROUTER_APP_NAME", "RAG GPT"),
    }

    payload = {
        "model": os.getenv("OPENROUTER_MODEL", "openai/gpt-4.1-mini"),
        "messages": messages,
        "temperature": temperature,
        "max_completion_tokens": max_tokens,
    }

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as error:
        details = ""
        if getattr(error, "response", None) is not None:
            details = f" {error.response.text[:300]}"
        raise LLMError(f"OpenRouter request failed.{details}") from error
    except ValueError as error:
        raise LLMError("OpenRouter returned an invalid response.") from error

    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise LLMError("OpenRouter response did not include an answer.") from error

    return (content or "").strip()
