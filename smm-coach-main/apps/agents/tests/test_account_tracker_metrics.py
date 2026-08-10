"""account_tracker prefers the OFFICIAL actualMetrics the web refresh-insights cron
writes (Graph reach/views/saves) over the datacenter-IP-blocked scraper. These cover
the _coerce_metrics parse + the _has_real_metrics gate that decides whether the
official row is usable — and, crucially, that an all-zero row (transient cron failure)
is NOT preferred, so we still fall back to the scraper instead of locking in zeros."""
from __future__ import annotations

import json

from app.graphs.nodes import account_tracker as at


def test_coerce_metrics_dict_str_none() -> None:
    assert at._coerce_metrics({"likes": 5}) == {"likes": 5}
    assert at._coerce_metrics(json.dumps({"reach": 100})) == {"reach": 100}
    assert at._coerce_metrics("") is None
    assert at._coerce_metrics(None) is None
    assert at._coerce_metrics("not json") is None
    assert at._coerce_metrics("[1,2]") is None  # valid JSON but not an object


def test_has_real_metrics_true_when_populated() -> None:
    assert at._has_real_metrics({"reach": 980}) is True
    assert at._has_real_metrics({"views": 1200}) is True
    assert at._has_real_metrics({"plays": 50}) is True
    assert at._has_real_metrics({"likes": 3}) is True
    assert at._has_real_metrics({"comments": 1}) is True


def test_has_real_metrics_false_when_empty_or_zero() -> None:
    assert at._has_real_metrics({}) is False
    assert at._has_real_metrics({"reach": 0, "views": 0, "likes": 0, "comments": 0}) is False
    # saves/shares alone don't count as "real" — without reach/views/likes/comments
    # the official row is effectively empty and the scraper fallback should run.
    assert at._has_real_metrics({"saves": 5, "shares": 2}) is False
