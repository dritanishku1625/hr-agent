from __future__ import annotations

import re
from typing import Any

from hr_agent.guard import find_injection_signals
from hr_agent.models import CandidateFacts, GroundingResult
from hr_agent.rubric import is_support_domain

_NAME = re.compile(r"^\s*([A-Za-z][A-Za-z'’.-]{0,40}?)\s+[—–\-]")
_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s+years?\b", re.I)
_WORD_YEARS = re.compile(
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s+years?\b",
    re.I,
)
_TICKETS = re.compile(r"(\d+)\s+tickets?\b", re.I)
_START = re.compile(r"start(?:\s+in)?\s+([^.]+)", re.I)
_FULL_TIME = re.compile(r"full[-\s]?time", re.I)
_WORD_YEAR_VALUES = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_KNOWN_TOOLS = (
    "zendesk",
    "freshdesk",
    "intercom",
    "gorgias",
    "salesforce",
    "kustomer",
    "help scout",
    "helpscout",
)
_KNOWN_LANGUAGES = (
    "english",
    "spanish",
    "french",
    "german",
    "italian",
    "portuguese",
    "albanian",
)
_OVERRIDE_KEYS = ("score", "instruction", "system", "action", "decision")
_TEXT_FIELDS = (
    "candidate_name",
    "support_domain",
    "employment_type",
    "start_timing",
)
_LIST_FIELDS = ("tools", "languages")


def parse_application(text: str, fallback_name: str) -> CandidateFacts:
    return CandidateFacts(
        candidate_name=_candidate_name(text, fallback_name),
        years_of_support_experience=_years(text),
        support_domain=_support_domain(text),
        tickets_per_day=_tickets(text),
        tools=_listed(_KNOWN_TOOLS, text),
        languages=_listed(_KNOWN_LANGUAGES, text),
        employment_type=_employment_type(text),
        start_timing=_start_timing(text),
    )


def ground_facts(model_payload: dict, source_text: str, fallback_name: str) -> GroundingResult:
    backup = parse_application(source_text, fallback_name)
    dropped = _drop_override_keys(model_payload)
    accepted_from_model: list[str] = []
    filled_from_backup: list[str] = []
    values: dict[str, Any] = {
        "candidate_name": backup.candidate_name,
        "years_of_support_experience": backup.years_of_support_experience,
        "support_domain": backup.support_domain,
        "tickets_per_day": backup.tickets_per_day,
        "tools": backup.tools,
        "languages": backup.languages,
        "employment_type": backup.employment_type,
        "start_timing": backup.start_timing,
    }

    _apply_text_fields(model_payload, source_text, values, accepted_from_model, dropped, filled_from_backup, backup)
    _apply_years(model_payload, source_text, values, accepted_from_model, dropped, filled_from_backup, backup)
    _apply_tickets(model_payload, source_text, values, accepted_from_model, dropped, filled_from_backup, backup)
    _apply_list_fields(model_payload, source_text, values, accepted_from_model, dropped, filled_from_backup, backup)

    return GroundingResult(
        facts=CandidateFacts(
            candidate_name=str(values["candidate_name"]),
            years_of_support_experience=float(values["years_of_support_experience"]),
            support_domain=str(values["support_domain"]),
            tickets_per_day=values["tickets_per_day"],
            tools=tuple(values["tools"]),
            languages=tuple(values["languages"]),
            employment_type=str(values["employment_type"]),
            start_timing=str(values["start_timing"]),
        ),
        accepted_from_model=accepted_from_model,
        dropped=dropped,
        filled_from_backup=filled_from_backup,
    )


def ungrounded_model_fields(model_payload: dict, source_text: str, accepted: CandidateFacts) -> list[str]:
    return ground_facts(model_payload, source_text, accepted.candidate_name).dropped


def evidence_quote_in_text(evidence: str, source_text: str) -> bool:
    quote = _normalize(evidence)
    source = _normalize(source_text)
    if not quote or len(quote) < 2:
        return False
    if find_injection_signals(evidence):
        return False
    return quote in source


def _apply_text_fields(payload, source_text, values, accepted, dropped, filled, backup) -> None:
    for key in _TEXT_FIELDS:
        field = payload.get(key)
        value, evidence = _split_evidenced(field)
        if value is None and evidence is None:
            if _backup_used(key, values, backup):
                filled.append(key)
            continue
        if not isinstance(value, str):
            dropped.append(f"{key}={value}")
            filled.append(key)
            continue
        cleaned = value.strip()
        if not cleaned:
            filled.append(key)
            continue
        if evidence is not None and evidence_quote_in_text(str(evidence), source_text):
            values[key] = _canonical_text_value(key, cleaned, str(evidence))
            accepted.append(key)
            continue
        if evidence is None and _normalize(cleaned) in _normalize(source_text):
            values[key] = cleaned
            accepted.append(key)
            continue
        dropped.append(_drop_label(key, cleaned, evidence))
        filled.append(key)


def _apply_years(payload, source_text, values, accepted, dropped, filled, backup) -> None:
    field = payload.get("years_of_support_experience")
    value, evidence = _split_evidenced(field)
    if value is None and evidence is None:
        if backup.years_of_support_experience:
            filled.append("years_of_support_experience")
        return
    number = _as_float(value)
    if number is None or number < 0 or number > 40:
        dropped.append(_drop_label("years_of_support_experience", value, evidence))
        filled.append("years_of_support_experience")
        return
    if evidence is not None and evidence_quote_in_text(str(evidence), source_text):
        values["years_of_support_experience"] = number
        accepted.append("years_of_support_experience")
        return
    if evidence is None and _years_mentioned(source_text, number):
        values["years_of_support_experience"] = number
        accepted.append("years_of_support_experience")
        return
    dropped.append(_drop_label("years_of_support_experience", value, evidence))
    filled.append("years_of_support_experience")


def _apply_tickets(payload, source_text, values, accepted, dropped, filled, backup) -> None:
    field = payload.get("tickets_per_day")
    value, evidence = _split_evidenced(field)
    if value is None and evidence is None:
        if backup.tickets_per_day is not None:
            filled.append("tickets_per_day")
        return
    number = _as_float(value)
    if number is None or number <= 0 or number > 500:
        if number == 0:
            values["tickets_per_day"] = None
            accepted.append("tickets_per_day")
            return
        dropped.append(_drop_label("tickets_per_day", value, evidence))
        filled.append("tickets_per_day")
        return
    if evidence is not None and evidence_quote_in_text(str(evidence), source_text):
        values["tickets_per_day"] = number
        accepted.append("tickets_per_day")
        return
    if evidence is None and _normalize(f"{_format_number(number)} tickets") in _normalize(source_text):
        values["tickets_per_day"] = number
        accepted.append("tickets_per_day")
        return
    dropped.append(_drop_label("tickets_per_day", value, evidence))
    filled.append("tickets_per_day")


def _apply_list_fields(payload, source_text, values, accepted, dropped, filled, backup) -> None:
    for key in _LIST_FIELDS:
        field = payload.get(key)
        value, evidence = _split_evidenced(field)
        if value is None and evidence is None:
            if getattr(backup, key):
                filled.append(key)
            continue
        if not isinstance(value, list):
            dropped.append(f"{key}={value}")
            filled.append(key)
            continue
        evidence_list = evidence if isinstance(evidence, list) else []
        kept = _keep_listed_items(value, evidence_list, source_text, key, dropped)
        if kept:
            values[key] = tuple(kept)
            accepted.append(key)
            continue
        if getattr(backup, key):
            filled.append(key)
            continue
        values[key] = ()


def _keep_listed_items(values: list, evidence_list: list, source_text: str, key: str, dropped: list[str]) -> list[str]:
    kept: list[str] = []
    for index, item in enumerate(values):
        if not isinstance(item, str) or not item.strip():
            continue
        cleaned = item.strip()
        quote = ""
        if index < len(evidence_list) and isinstance(evidence_list[index], str):
            quote = evidence_list[index].strip()
        if quote and evidence_quote_in_text(quote, source_text):
            kept.append(cleaned)
            continue
        if _normalize(cleaned) in _normalize(source_text):
            kept.append(cleaned)
            continue
        dropped.append(_drop_label(f"{key}[{index}]", cleaned, quote or None))
    return kept


def _split_evidenced(field: object) -> tuple[object | None, object | None]:
    if isinstance(field, dict):
        return field.get("value"), field.get("evidence")
    if field is None:
        return None, None
    return field, None


def _drop_override_keys(payload: dict) -> list[str]:
    if not payload:
        return []
    dropped = []
    for key in _OVERRIDE_KEYS:
        if key in payload:
            dropped.append(f"{key}={payload[key]}")
    return dropped


def _backup_used(key: str, values: dict, backup: CandidateFacts) -> bool:
    backup_value = getattr(backup, key)
    if isinstance(backup_value, str):
        return bool(backup_value)
    if isinstance(backup_value, tuple):
        return bool(backup_value)
    return backup_value not in (None, 0, 0.0)


def _drop_label(key: str, value: object, evidence: object) -> str:
    if evidence is None:
        return f"{key}={value}"
    return f"{key}={value} evidence={evidence}"


def _years_mentioned(source_text: str, number: float) -> bool:
    if _normalize(f"{_format_number(number)} years") in _normalize(source_text):
        return True
    for word, value in _WORD_YEAR_VALUES.items():
        if abs(value - number) < 0.01 and _normalize(f"{word} years") in _normalize(source_text):
            return True
    return False


def _candidate_name(text: str, fallback_name: str) -> str:
    match = _NAME.search(text)
    if not match:
        return fallback_name
    return match.group(1).strip()


def _years(text: str) -> float:
    digit = _YEARS.search(text)
    if digit:
        value = float(digit.group(1))
        if 0 < value <= 40:
            return value
    word = _WORD_YEARS.search(text)
    if not word:
        return 0
    return float(_WORD_YEAR_VALUES[word.group(1).lower()])


def _tickets(text: str) -> float | None:
    match = _TICKETS.search(text)
    if not match:
        return None
    value = float(match.group(1))
    if value <= 0 or value > 500:
        return None
    return value


def _support_domain(text: str) -> str:
    lowered = text.lower()
    if "call centre" in lowered or "call center" in lowered:
        return "telecom call centre" if "telecom" in lowered else "call centre"
    if "e-commerce support" in lowered or "ecommerce support" in lowered:
        return "e-commerce support"
    if "customer support" in lowered or "customer service" in lowered:
        return "customer support"
    if "helping customers" in lowered:
        return "helping customers"
    if "support" in lowered:
        return "support"
    return ""


def _listed(known: tuple[str, ...], text: str) -> tuple[str, ...]:
    lowered = text.lower()
    return tuple(item for item in known if item in lowered)


def _employment_type(text: str) -> str:
    if _FULL_TIME.search(text):
        return "full-time"
    return ""


def _start_timing(text: str) -> str:
    match = _START.search(text)
    if not match:
        return ""
    return match.group(1).strip()


def _canonical_text_value(key: str, value: str, evidence: str) -> str:
    if key != "support_domain":
        return value
    if is_support_domain(value):
        return value
    if is_support_domain(evidence):
        return " ".join(evidence.split())[:120]
    return value


def _normalize(text: str) -> str:
    return " ".join(text.casefold().split())


def _as_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _format_number(value: float) -> str:
    if value == int(value):
        return str(int(value))
    return str(value)
