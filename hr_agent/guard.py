from __future__ import annotations

import re

_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(?:your\s+|the\s+|all\s+)?(?:rubric|instructions|rules|previous)", re.I),
    re.compile(r"system\s+note", re.I),
    re.compile(r"confidential\s+hr\s+update", re.I),
    re.compile(r"score\s+of\s+100", re.I),
    re.compile(r"advance\s+this\s+candidate", re.I),
    re.compile(r"disregard\s+(?:your\s+|the\s+)?(?:rubric|instructions|rules)", re.I),
    re.compile(r"verified\s+seniority", re.I),
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!;])\s+|\n+")


def find_injection_signals(text: str) -> list[str]:
    return [pattern.pattern for pattern in _INJECTION_PATTERNS if pattern.search(text)]


def strip_injection_sentences(text: str) -> str:
    parts = [part.strip() for part in _SENTENCE_SPLIT.split(text) if part.strip()]
    kept = [part for part in parts if not find_injection_signals(part)]
    if not kept:
        return text
    return " ".join(kept)
