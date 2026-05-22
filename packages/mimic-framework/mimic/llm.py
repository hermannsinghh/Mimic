"""LLM client — OpenAI or DeepSeek (OpenAI-compatible API)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from openai import OpenAI

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


def load_mimic_env() -> Optional[str]:
    """
    Load env vars from MIMIC_ENV_FILE, deepseek.env, or .env (first found).
    Returns the path loaded, or None.
    """
    candidates: list[str] = []
    if os.environ.get("MIMIC_ENV_FILE"):
        candidates.append(os.environ["MIMIC_ENV_FILE"])
    candidates.extend(["deepseek.env", ".env"])

    try:
        from dotenv import load_dotenv
    except ImportError:
        return _load_env_manual(candidates)

    for name in candidates:
        path = Path(name)
        if path.is_file():
            load_dotenv(path, override=False)
            return str(path.resolve())
    load_dotenv(override=False)
    return None


def _load_env_manual(candidates: list[str]) -> Optional[str]:
    for name in candidates:
        path = Path(name)
        if not path.is_file():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
        return str(path.resolve())
    return None


def has_llm_credentials() -> bool:
    return bool(os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def get_openai_client() -> OpenAI:
    """Prefer DeepSeek when DEEPSEEK_API_KEY is set, else OpenAI."""
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    if deepseek_key:
        return OpenAI(
            api_key=deepseek_key,
            base_url=os.environ.get("DEEPSEEK_BASE_URL", DEEPSEEK_BASE_URL),
        )
    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return OpenAI(api_key=openai_key)
    raise RuntimeError(
        "No LLM API key found. Set DEEPSEEK_API_KEY in deepseek.env or OPENAI_API_KEY in .env."
    )


def default_chat_model() -> str:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    return os.environ.get("OPENAI_MODEL", "gpt-4o")


def default_extraction_model() -> str:
    if os.environ.get("DEEPSEEK_API_KEY"):
        return os.environ.get("DEEPSEEK_EXTRACTION_MODEL", "deepseek-chat")
    return "gpt-4o-mini"
