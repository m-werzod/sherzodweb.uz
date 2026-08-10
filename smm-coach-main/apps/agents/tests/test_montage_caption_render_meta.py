"""Faza D — caption_stylist._render_meta: the final_render meta carries the optional inpaint target
(so the workflow input's inpaint_remove rides state → meta.inpaintRemove → worker → inpaint)."""
from __future__ import annotations

from app.graphs.nodes.caption_stylist import _render_meta, _sanitize
from app.montage.compiler import _caption_params

_SPEC = {"size": 96, "accent": "amber", "tier": "premium", "emphasis_words": [], "hook_overlay": ""}


def test_render_meta_font_defaults_montserrat() -> None:
    assert _render_meta(_SPEC, None)["captionStyle"]["font"] == "Montserrat"


def test_render_meta_carries_chosen_font() -> None:
    assert _render_meta({**_SPEC, "font": "Anton"}, None)["captionStyle"]["font"] == "Anton"


def test_sanitize_allows_bundled_trend_font() -> None:
    assert _sanitize({"font": "Bebas Neue"})["font"] == "Bebas Neue"
    assert _sanitize({"font": "Oswald"})["font"] == "Oswald"


def test_sanitize_rejects_unknown_font() -> None:
    # An uninstalled face would make libass fall back to a system serif → force Montserrat.
    assert _sanitize({"font": "Comic Sans"})["font"] == "Montserrat"
    assert _sanitize({})["font"] == "Montserrat"


def test_compiler_reads_font_from_caption_spec() -> None:
    style, _tier, _emph = _caption_params({"style": {"font": "Anton", "size": 96}})
    assert style is not None and style.font == "Anton"
    # unknown font → keep the Montserrat default (never a blind libass fallback)
    style2, _t, _e = _caption_params({"style": {"font": "Wingdings"}})
    assert style2 is not None and style2.font == "Montserrat"


def test_render_meta_has_caption_style_always() -> None:
    m = _render_meta(_SPEC, None)
    assert m["tier"] == "premium"
    assert m["captionStyle"]["size"] == 96
    assert "inpaintRemove" not in m


def test_render_meta_includes_inpaint_when_present() -> None:
    assert _render_meta(_SPEC, "person in background")["inpaintRemove"] == "person in background"
    assert _render_meta(_SPEC, "  logo  ")["inpaintRemove"] == "logo"


def test_render_meta_omits_inpaint_when_blank() -> None:
    assert "inpaintRemove" not in _render_meta(_SPEC, "")
    assert "inpaintRemove" not in _render_meta(_SPEC, "   ")
    assert "inpaintRemove" not in _render_meta(_SPEC, None)


def test_render_meta_includes_decor_when_present() -> None:
    assert _render_meta(_SPEC, None, "modern neon studio")["decorBackground"] == "modern neon studio"
    assert "decorBackground" not in _render_meta(_SPEC, None, None)
    assert "decorBackground" not in _render_meta(_SPEC, None, "   ")
