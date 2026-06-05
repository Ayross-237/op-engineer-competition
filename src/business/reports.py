"""Domain types for computed catering sessions.

These dataclasses carry a session's computed state between the compute step
(build_session_report / compute_caterer_sessions) and the markdown renderers,
so the rendering code never re-runs the non-deterministic dish selection.
"""
from dataclasses import dataclass, field


@dataclass
class SessionReport:
    """The fully-computed view of one session, ready for rendering."""
    student_count: int
    standard_counts: dict[str, int] = field(default_factory=dict)
    special_assignments: list[tuple[str, str]] = field(default_factory=list)  # (requirements label, dish)
    cost: float = 0.0
    pricing: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class RenderedSession:
    """One computed session, ready to render into either document. The non-deterministic
    `report` is built once (in compute_caterer_sessions) and reused for both copies."""
    school_name: str
    header: str          # e.g. "2026-05-02 (Tuesday 16:00–19:00)"
    building: str
    dinner: str
    manager_line: str
    total_count: int     # students on the roster (incl. opted-out)
    opted_out_count: int
    report: SessionReport
