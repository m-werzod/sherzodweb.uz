"""Clean up stale half-onboarded users.

When a visitor signs up but never completes the onboarding wizard
(closes the tab on the niche question), the User + Tenant rows remain
in DB. On a retry they get an "email_in_use" error and can't restart.

Daily job:
  • Find Users older than 45 days with NO OnboardingProfile, NO completed
    AgentRun, NO InstagramAccount, NO Roadmap (i.e. touched nothing meaningful).
  • Cascade-delete their Tenant (User goes with it via FK).

We're conservative — anything with even one trace of activity is kept.

CRITICAL: the age threshold MUST exceed the Auth.js JWT lifetime (30 days).
A user holds a stateless 30-day session cookie; deleting their tenant earlier
leaves a "ghost session" — a valid JWT whose tenantId no longer exists — and
the next tenant-scoped write (e.g. instagram_accounts.create) FK-violates.
So we wait 45 days, by which point any such session has expired.
"""
from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import text

from app.integrations import telegram
from app.memory.db import get_sessionmaker

log = structlog.get_logger(__name__)

TICK_INTERVAL_SEC = 6 * 60 * 60  # every 6 hours


_BATCH_SIZE = 100
_MAX_BATCHES = 50  # absolute safety cap: ≤5000 tenants purged per tick


async def _tick() -> int:
    """Delete stale half-onboarded tenants in committed batches.

    A single unbounded `DELETE ... RETURNING` with FK cascades could lock/bloat
    if a backlog ever accumulates. We delete in chunks of _BATCH_SIZE, commit
    each chunk (releasing locks between them), and stop once a short batch shows
    the set is drained — bounded by _MAX_BATCHES as a backstop.
    """
    sm = get_sessionmaker()
    total = 0
    async with sm() as session:
        for _ in range(_MAX_BATCHES):
            result = await session.execute(
                text(
                    """
                    DELETE FROM tenants
                    WHERE id IN (
                      SELECT t.id FROM tenants t
                      WHERE t."createdAt" < NOW() - INTERVAL '45 days'
                        AND NOT EXISTS (SELECT 1 FROM onboarding_profiles op WHERE op."tenantId" = t.id)
                        AND NOT EXISTS (SELECT 1 FROM agent_runs ar WHERE ar."tenantId" = t.id AND ar.status IN ('completed', 'running'))
                        AND NOT EXISTS (SELECT 1 FROM instagram_accounts ia WHERE ia."tenantId" = t.id)
                        AND NOT EXISTS (SELECT 1 FROM roadmaps r WHERE r."tenantId" = t.id)
                      LIMIT :batch
                    )
                    RETURNING id
                    """
                ),
                {"batch": _BATCH_SIZE},
            )
            n = len(result.fetchall())
            await session.commit()
            total += n
            if n < _BATCH_SIZE:
                break
    return total


async def run_forever() -> None:
    log.info("orphan_cleanup.start", interval_sec=TICK_INTERVAL_SEC)
    while True:
        try:
            count = await _tick()
            if count:
                log.info("orphan_cleanup.batch", deleted=count)
                telegram.send(f"🧹 Tozalash · {count} ta eskirgan (yarim onboard) tenant o'chirildi")
        except Exception:  # noqa: BLE001
            log.exception("orphan_cleanup.tick_failed")
        await asyncio.sleep(TICK_INTERVAL_SEC)
