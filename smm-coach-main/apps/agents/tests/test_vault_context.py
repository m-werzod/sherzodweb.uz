from __future__ import annotations

from app.memory.vault_context import format_vault_block

H = "TEST HEADER"


def test_empty_notes_is_empty_block():
    # pre-existing tenants with no vault → prompt must be byte-identical
    assert format_vault_block([], H) == ""
    assert format_vault_block([{"title": "x", "body": "  "}], H) == ""


def test_block_includes_header_kind_and_title():
    out = format_vault_block(
        [{"kind": "lessons_learned", "title": "Sikl 1", "body": "Reels ishladi"}], H
    )
    assert "--- TEST HEADER ---" in out
    assert "[lessons_learned] Sikl 1: Reels ishladi" in out


def test_body_truncated_to_240():
    out = format_vault_block([{"kind": "story", "title": "T", "body": "x" * 1000}], H)
    assert "x" * 240 in out
    assert "x" * 241 not in out


def test_caps_to_six_notes():
    notes = [{"kind": "n", "title": f"T{i}", "body": f"b{i}"} for i in range(12)]
    assert format_vault_block(notes, H).count("\n- ") == 6


def test_skips_bodyless_notes_keeps_others():
    out = format_vault_block(
        [{"kind": "a", "title": "A", "body": ""}, {"kind": "b", "title": "B", "body": "real"}], H
    )
    assert "B: real" in out
    assert "[a]" not in out
