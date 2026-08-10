"""Guard test for the lead/comment pulse fix: a stored shortcode must not crash
media_comments() via int('Cabc123'). _media_pk coerces every stored identifier form
to the numeric pk instagrapi needs."""
from app.integrations.instagram.instagrapi_client import _media_pk


class _FakeClient:
    def media_pk_from_code(self, code: str) -> int:  # pure local decode in real instagrapi
        assert code == "Cabc123"
        return 99999


def test_numeric_pk_passthrough():
    assert _media_pk(_FakeClient(), "1234567890") == 1234567890


def test_media_id_form_keeps_pk_part():
    assert _media_pk(_FakeClient(), "1234567890_42") == 1234567890


def test_shortcode_is_converted_not_int_cast():
    # the bug: int('Cabc123') raised ValueError. Now it routes to media_pk_from_code.
    assert _media_pk(_FakeClient(), "Cabc123") == 99999


def test_whitespace_stripped():
    assert _media_pk(_FakeClient(), "  1234567890  ") == 1234567890
