from __future__ import annotations

from hr_agent.guard import find_injection_signals

DECISION_TOOL_NAMES = ("advance_to_interview", "reject", "request_more_info")


def execute_decision(
    tool_name: str,
    candidate_name: str,
    score: int,
    reason: str,
    questions: list[str],
) -> dict:
    if tool_name == "advance_to_interview":
        return advance_to_interview(candidate_name, score, reason)
    if tool_name == "reject":
        return reject(candidate_name, score, reason)
    if tool_name == "request_more_info":
        return request_more_info(candidate_name, score, reason, questions)
    raise ValueError(f"Unknown tool: {tool_name}")


def advance_to_interview(candidate_name: str, score: int, reason: str) -> dict:
    return {
        "tool": "advance_to_interview",
        "candidate_name": candidate_name,
        "score": score,
        "reason": reason,
        "status": "advanced_to_interview",
    }


def reject(candidate_name: str, score: int, reason: str) -> dict:
    return {
        "tool": "reject",
        "candidate_name": candidate_name,
        "score": score,
        "reason": reason,
        "status": "waiting_for_human_approval",
        "proposed_outcome": "reject",
        "human_approved": False,
    }


def request_more_info(candidate_name: str, score: int, reason: str, questions: list[str]) -> dict:
    return {
        "tool": "request_more_info",
        "candidate_name": candidate_name,
        "score": score,
        "reason": reason,
        "questions": questions,
        "status": "waiting_for_more_information",
    }


def questions_for_request(proposed: object, fallback: list[str]) -> list[str]:
    if not isinstance(proposed, list):
        return fallback
    cleaned = [question for question in (_clean_question(item) for item in proposed) if question]
    if not cleaned:
        return fallback
    return cleaned[:4]


def reason_for_decision(proposed: object, fallback: str) -> str:
    if not isinstance(proposed, str):
        return fallback
    reason = " ".join(proposed.split())
    if not reason or len(reason) > 280:
        return fallback
    if find_injection_signals(reason):
        return fallback
    return reason


def _clean_question(item: object) -> str:
    if not isinstance(item, str):
        return ""
    question = " ".join(item.split())
    if not question or len(question) > 240:
        return ""
    if find_injection_signals(question):
        return ""
    return question
