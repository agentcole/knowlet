from __future__ import annotations

import re

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
}

_LANGUAGE_PATTERN = re.compile(r"^[a-z]{2}(?:-[a-z]{2})?$")


def normalize_language(value: str | None) -> str:
    if not value:
        return DEFAULT_LANGUAGE

    code = value.strip().lower()
    if code in SUPPORTED_LANGUAGES:
        return code

    if _LANGUAGE_PATTERN.match(code):
        base = code.split("-", 1)[0]
        if base in SUPPORTED_LANGUAGES:
            return base

    return DEFAULT_LANGUAGE


def language_name(code: str | None) -> str:
    normalized = normalize_language(code)
    return SUPPORTED_LANGUAGES.get(normalized, SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])
