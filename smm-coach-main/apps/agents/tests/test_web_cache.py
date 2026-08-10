"""Stage 3b — web-result caching: pins the pure row-shaping (dedup by url,
empties dropped, cap, snippet-preferred content)."""
from __future__ import annotations

from app.memory.shared_knowledge import _shape_web_rows


def test_empty():
    assert _shape_web_rows([]) == []


def test_drops_empty_content():
    rows = _shape_web_rows([{"title": "", "snippet": "", "url": "https://a.com"}])
    assert rows == []


def test_prefers_snippet_over_title():
    rows = _shape_web_rows([{"title": "T", "snippet": "S", "url": "https://a.com"}])
    assert rows[0]["content"] == "S"
    assert rows[0]["headline"] == "T"


def test_falls_back_to_title_when_no_snippet():
    rows = _shape_web_rows([{"title": "Only title", "snippet": "", "url": "https://a.com"}])
    assert rows[0]["content"] == "Only title"


def test_dedup_by_url():
    rows = _shape_web_rows(
        [
            {"title": "A", "snippet": "x", "url": "https://a.com"},
            {"title": "B", "snippet": "y", "url": "https://a.com"},
            {"title": "C", "snippet": "z", "url": "https://c.com"},
        ]
    )
    assert [r["url"] for r in rows] == ["https://a.com", "https://c.com"]


def test_caps_at_8():
    rows = _shape_web_rows(
        [{"title": f"T{i}", "snippet": f"s{i}", "url": f"https://{i}.com"} for i in range(20)]
    )
    assert len(rows) == 8
