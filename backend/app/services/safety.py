import re

from app.core.config import get_settings
from app.utils.text import normalize_text

settings = get_settings()

INJECTION_REGEXES = [
    re.compile(r"\bignore\b.*\binstruction"),
    re.compile(r"\bbo qua\b.*\bhuong dan\b"),
    re.compile(r"\bbypass\b.*\bguard"),
    re.compile(r"\bdong vai\b.*\bhacker\b"),
    re.compile(r"\b(system prompt|prompt he thong)\b"),
    re.compile(r"\b(reveal|show|display|tiet lo)\b.*\b(ma nguon|source code|code|system prompt)\b"),
]

INJECTION_KEYWORDS = {
    "ma nguon",
    "source code",
    "prompt he thong",
    "system prompt",
    "dong vai mot hacker",
}


def sanitize_user_input(text: str) -> tuple[str, bool]:
    cleaned = re.sub(r"\s+", " ", text).strip()
    lowered = normalize_text(cleaned)

    flagged = any(pattern in lowered for pattern in settings.prompt_injection_patterns)
    if not flagged:
        flagged = any(regex.search(lowered) for regex in INJECTION_REGEXES)
    if not flagged:
        flagged = any(keyword in lowered for keyword in INJECTION_KEYWORDS)

    return cleaned, flagged
