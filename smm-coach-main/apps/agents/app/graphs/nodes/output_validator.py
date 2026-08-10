"""Last gate before tasks go to the user. Enforces the "no claim without
evidence" rule: every concrete metric/timing claim in the script must be
either backed by `predict_evidence` or removed.
"""
from __future__ import annotations

import re

import structlog

from app.graphs.state import GrowthCoachState
from app.streams.bus import publish

log = structlog.get_logger(__name__)

# Heuristic: numerical engagement/growth claims without a citation marker.
# We only flag CLEARLY-fabricated quantitative promises — Claude routinely
# uses soft phrasing like "ko'proq engagement" or "obunachi o'sishi" which
# is fine. The pattern below catches things like:
#   - "100K follower in 2 hafta"
#   - "5x more reach"
#   - "guaranteed 1000 followers"
# Plain percentages without growth verbs (e.g. "70% audio sokin") are NOT flagged.
CLAIM_PATTERNS = (
    # Specific follower / view counts pinned to a short time window
    re.compile(
        r"\b\d{2,}\s*(?:K|M|ming|million|min)?\s*(?:follower|obunachi|view|ko[’']?rilgan)\b.*\b\d+\s*(?:soat|kun|hafta|oy|hour|day|week|month)\b",
        re.I | re.S,
    ),
    # "Nx" multiplier claims (e.g. "5x more reach")
    re.compile(r"\b\d+x\b.*\b(more|ko[’']?proq|engagement|reach|qamrov)\b", re.I),
    # Marketing absolutes
    re.compile(r"\b(guaranteed|kafolatlangan|kafolat beraman|100%\s*growth)\b", re.I),
)
CITATION_MARKER = "@evidence:"


async def run(state: GrowthCoachState) -> dict:
    proposals = state.get("proposed_tasks") or []
    if not proposals:
        return {}

    errors: list[dict] = []
    valid: list[dict] = []
    rejected: list[dict] = []

    for task in proposals:
        script = task.get("script_md") or task.get("scriptMd") or ""
        evidence = task.get("predict_evidence") or task.get("predictEvidence")
        bad = []
        for pat in CLAIM_PATTERNS:
            for m in pat.finditer(script):
                snippet = m.group(0)
                if CITATION_MARKER in script or evidence:
                    continue
                bad.append(snippet)
        if bad:
            errors.append({"task_title": task.get("title"), "ungrounded_claims": bad})
            rejected.append(task)
        else:
            valid.append(task)

    log.info(
        "validator.results",
        input=len(proposals),
        approved=len(valid),
        rejected=len(rejected),
        errors=len(errors),
    )
    if errors:
        log.warning("validator.rejected", count=len(errors))
        run_id = state["run_id"]
        user_id = state.get("user_id") or "system"
        await publish(
            user_id,
            {
                "type": "agent.thinking",
                "runId": run_id,
                "agent": "output_validator",
                "note": f"{len(errors)} ta vazifada dalilsiz da'vo topildi — qayta yozish kerak",
                "at": _now(),
            },
        )

    # If there are validation errors, leave the rejected tasks in
    # `proposed_tasks` so scriptwriter can rewrite them next iteration.
    # Otherwise clear so we don't double-process accepted tasks.
    next_proposed = rejected if errors else []
    return {
        "validation_errors": errors,
        "approved_tasks": valid,
        "rejected_tasks": rejected,
        "proposed_tasks": next_proposed,
    }


def _now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
