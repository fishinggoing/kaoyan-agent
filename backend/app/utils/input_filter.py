"""Lightweight input filter for user-submitted text that reaches LLM prompts.

Does NOT sanitize HTML or full user content — that's the frontend's job.
Focuses on LLM-specific injection patterns and resource abuse.
"""

import re

MAX_MESSAGE_LENGTH = 4_000      # per-message limit
MAX_HISTORY_MESSAGES = 40       # conversation history cap
MAX_TOTAL_CHARS = 32_000        # total characters across history + message

# Patterns that suggest prompt injection / jailbreak attempts
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions?", re.I),
    re.compile(r"system\s*:\s*(you\s+are|your\s+role)", re.I),
    re.compile(r"\[INST\].*\[/INST\]", re.I),          # Llama/Mistral format
    re.compile(r"<\|im_start\|>|<\|im_end\|>", re.I),  # ChatML format
    re.compile(r"DAN\s*Mode|Developer\s*Mode|jailbreak", re.I),
    re.compile(r"pretend|角色扮演|忽略.+系统|忽略.+规则|越狱|破解模式", re.I),
]


def contains_injection(text: str) -> bool:
    """Check if text matches known prompt injection patterns."""
    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            return True
    return False


def sanitize_for_llm(text: str) -> str:
    """Strip control characters (except common whitespace) from text."""
    # Remove null bytes, form feed, vertical tab, and other control chars
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return cleaned[:MAX_MESSAGE_LENGTH]


def validate_chat_input(message: str, history: list[dict[str, str]]) -> str | None:
    """Validate user chat input. Returns error message string or None if valid.

    Checks:
      - message length under MAX_MESSAGE_LENGTH
      - history message count under MAX_HISTORY_MESSAGES
      - total character count under MAX_TOTAL_CHARS
      - no prompt injection patterns in current message
    """
    msg = (message or "").strip()
    if not msg:
        return "Message cannot be empty"

    if len(msg) > MAX_MESSAGE_LENGTH:
        return f"Message too long (max {MAX_MESSAGE_LENGTH} characters)"

    # Count history
    h = history or []
    if len(h) > MAX_HISTORY_MESSAGES:
        return f"Too many conversation turns (max {MAX_HISTORY_MESSAGES})"

    total_chars = sum(len(m.get("content", "")) for m in h) + len(msg)
    if total_chars > MAX_TOTAL_CHARS:
        return "Conversation too long — please start a new session"

    if contains_injection(msg):
        return "Input contains disallowed patterns"

    return None
