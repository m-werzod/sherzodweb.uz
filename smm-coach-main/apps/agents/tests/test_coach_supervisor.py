from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.workers.coach_supervisor import _RESEND_AFTER_DAYS, _recently_sent, should_autopilot_replan


def test_off_by_default():
    # autopilot off → never auto-replan, even with an open underperform
    assert should_autopilot_replan(False, True, None) is False


def test_needs_open_underperform():
    assert should_autopilot_replan(True, False, None) is False


def test_fires_when_on_open_and_no_prior_replan():
    assert should_autopilot_replan(True, True, None) is True


def test_respects_cooldown():
    assert should_autopilot_replan(True, True, 2.0) is False  # 2h < 6h cooldown
    assert should_autopilot_replan(True, True, 6.0) is True
    assert should_autopilot_replan(True, True, 9.0) is True


def test_weekly_cap_stops_endless_auto_replans():
    # Past the cooldown but already at the weekly cap → no more auto-replans this week.
    assert should_autopilot_replan(True, True, 9.0, replans_this_week=3) is False
    assert should_autopilot_replan(True, True, 9.0, replans_this_week=2) is True
    # custom cap honoured
    assert should_autopilot_replan(True, True, 9.0, replans_this_week=1, max_per_week=1) is False


@pytest.mark.asyncio
async def test_recently_sent_binds_days_as_int_not_text():
    """Regression: the resend-window query concatenated the INT :d straight into '||' — asyncpg
    then inferred :d as text and crashed (`$3: 3 expected str, got int`) on EVERY tenant, so the
    dedup check threw and NO coach reminder ever emitted. The int must feed a CAST(... AS int) so
    Postgres types the bind param as int (matches account_tracker/comment_sentinel/prediction_resolver).
    Lock the SQL shape + the int-typed param so the interval math can never regress to a text bind."""
    result = MagicMock()
    result.scalar.return_value = None
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)

    await _recently_sent(session, "tenant-x", "some reminder text")

    clause, params = session.execute.call_args.args
    sql = str(clause)
    # The param must be typed int by the query so asyncpg binds an integer, not text.
    assert "CAST(:d AS int)" in sql
    assert "(:d || ' days')" not in sql  # the crashing bare-concat form is gone
    assert isinstance(params["d"], int) and params["d"] == _RESEND_AFTER_DAYS
