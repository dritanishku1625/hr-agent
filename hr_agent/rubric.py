from __future__ import annotations

import re

from hr_agent.models import CandidateFacts, ScoreBreakdown

_FULL_TIME = re.compile(r"full[-\s]?time", re.I)
_SOON = (
    "week",
    "immediately",
    "today",
    "tomorrow",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "asap",
)
_SUPPORT_MARKERS = (
    "support",
    "call centre",
    "call center",
    "help desk",
    "helpdesk",
    "customer service",
    "helping customers",
    "customer care",
    "inbox",
)


def is_support_domain(domain: str) -> bool:
    lowered = domain.lower()
    return any(marker in lowered for marker in _SUPPORT_MARKERS)


def score_candidate(facts: CandidateFacts) -> ScoreBreakdown:
    return ScoreBreakdown(
        experience=_experience_points(facts),
        tools=_tool_points(facts),
        output=_output_points(facts),
        languages=_language_points(facts),
        availability=_availability_points(facts),
        clarity=_clarity_points(facts),
    )


def one_line_reason(facts: CandidateFacts, breakdown: ScoreBreakdown) -> str:
    experience = _experience_phrase(facts)
    return (
        f"{breakdown.total}/100 because the application shows {experience}; "
        f"tools {breakdown.tools}/15, ticket volume {breakdown.output}/15, "
        f"languages {breakdown.languages}/15, availability {breakdown.availability}/10."
    )


def missing_questions(facts: CandidateFacts) -> list[str]:
    questions = []
    if facts.years_of_support_experience <= 0 or not is_support_domain(facts.support_domain):
        questions.append("How many years have you worked in customer support, and what kind of team was it?")
    if not facts.tools:
        questions.append("Which support tools have you used, such as Zendesk or a similar helpdesk?")
    if not facts.tickets_per_day:
        questions.append("How many tickets or chats did you handle on a typical day?")
    if "english" not in {language.lower() for language in facts.languages}:
        questions.append("Which languages can you support customers in, and how strong is your English?")
    if not _FULL_TIME.search(facts.employment_type) or not facts.start_timing:
        questions.append("Are you available full-time, and when could you start?")
    return questions


def _experience_points(facts: CandidateFacts) -> int:
    if facts.years_of_support_experience <= 0 or not is_support_domain(facts.support_domain):
        return 0
    years = facts.years_of_support_experience
    if years < 1:
        return 10
    if years < 2:
        return 20
    if years < 3:
        return 25
    return 35


def _tool_points(facts: CandidateFacts) -> int:
    if facts.tools:
        return 15
    return 0


def _output_points(facts: CandidateFacts) -> int:
    tickets = facts.tickets_per_day
    if tickets is None or tickets <= 0:
        return 0
    if tickets >= 40:
        return 15
    if tickets >= 20:
        return 10
    return 5


def _language_points(facts: CandidateFacts) -> int:
    languages = {language.lower() for language in facts.languages}
    if "english" not in languages:
        return 0
    extras = len(languages - {"english"})
    return min(15, 10 + extras * 5)


def _availability_points(facts: CandidateFacts) -> int:
    points = 0
    if _FULL_TIME.search(facts.employment_type):
        points += 6
    if _starts_soon(facts.start_timing):
        points += 4
    return points


def _clarity_points(facts: CandidateFacts) -> int:
    points = 0
    if facts.years_of_support_experience > 0 and facts.support_domain:
        points += 4
    if facts.tickets_per_day:
        points += 2
    if facts.tools:
        points += 2
    if facts.languages:
        points += 2
    return min(10, points)


def _experience_phrase(facts: CandidateFacts) -> str:
    if facts.years_of_support_experience <= 0 or not facts.support_domain:
        return "no relevant support experience"
    years = _format_years(facts.years_of_support_experience)
    return f"{years} years in {facts.support_domain}"


def _starts_soon(start_timing: str) -> bool:
    lowered = start_timing.lower()
    if "weekend" in lowered:
        return False
    return any(token in lowered for token in _SOON)


def _format_years(years: float) -> str:
    if years == int(years):
        return str(int(years))
    return str(years)
