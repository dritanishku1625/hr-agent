from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateFacts:
    candidate_name: str
    years_of_support_experience: float
    support_domain: str
    tickets_per_day: float | None
    tools: tuple[str, ...]
    languages: tuple[str, ...]
    employment_type: str
    start_timing: str


@dataclass(frozen=True)
class ScoreBreakdown:
    experience: int
    tools: int
    output: int
    languages: int
    availability: int
    clarity: int

    @property
    def total(self) -> int:
        return (
            self.experience
            + self.tools
            + self.output
            + self.languages
            + self.availability
            + self.clarity
        )


@dataclass(frozen=True)
class GroundingResult:
    facts: CandidateFacts
    accepted_from_model: list[str]
    dropped: list[str]
    filled_from_backup: list[str]
