ADVANCE_MINIMUM = 70
MORE_INFO_MINIMUM = 20


def action_for_score(score: int) -> str:
    if score >= ADVANCE_MINIMUM:
        return "advance_to_interview"
    if score >= MORE_INFO_MINIMUM:
        return "request_more_info"
    return "reject"


def rules_text() -> str:
    upper = ADVANCE_MINIMUM - 1
    lower = MORE_INFO_MINIMUM - 1
    return (
        f"Call advance_to_interview when rubric_score is {ADVANCE_MINIMUM} or higher. "
        f"Call request_more_info when rubric_score is {MORE_INFO_MINIMUM} to {upper}. "
        f"Call reject when rubric_score is {lower} or lower."
    )
