"""Gemini wrapper for Market Analyst (Flash) and vision tasks."""
from __future__ import annotations

import asyncio
import contextlib
import os
import tempfile
import time
from typing import Any

import structlog
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.budget.guard import DEGRADE_MAP, kill_switch_on, over_cap
from app.budget.guard import degrade as degrade_model
from app.config import get_settings
from app.graphs.state import CostLedger
from app.integrations.llm.pricing import cost_usd
from app.runs.context import current as current_run
from app.runs.llm_inspector import record_llm_call
from app.runs.repository import record_token_usage
from app.streams.bus import publish

log = structlog.get_logger(__name__)

_client: genai.Client | None = None

# Free-tier Gemini 2.5 Flash allows ~10 requests/minute. We serialize calls
# through a process-wide lock and enforce a 7s gap between them so a roadmap
# run (which fires 3-4 LLM calls in sequence) doesn't blow through the quota.
# Production tier removes this lock by setting GEMINI_MIN_GAP_S=0 in env.
_call_lock = asyncio.Lock()
_last_call_ts = 0.0
# Free tier ratelimits Flash at ~10 req/min, so we serialize with a 7s gap.
# Paid tier (billing enabled) has far higher RPM — set GEMINI_MIN_GAP_S=0 (or a
# small value like 0.2) in env to remove the bottleneck.
_MIN_GAP_S = float(os.getenv("GEMINI_MIN_GAP_S") or "7.0")


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        key = get_settings().gemini_api_key
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not configured")
        _client = genai.Client(api_key=key.get_secret_value())
    return _client


def _should_retry_gemini(exc: BaseException) -> bool:
    """Retry only on transient failures. 4xx ClientError (quota, invalid
    request) won't fix itself in 60s so we propagate immediately — the node
    will fall through to its template fallback."""
    if isinstance(exc, genai_errors.ClientError):
        return False
    return isinstance(
        exc,
        (TimeoutError, ConnectionError, genai_errors.ServerError),
    )


@retry(
    retry=retry_if_exception(_should_retry_gemini),
    wait=wait_exponential_jitter(initial=4, max=60),
    stop=stop_after_attempt(3),
    reraise=True,
)
async def _generate(model: str, contents: list, config: genai_types.GenerateContentConfig):
    # Serialize through the global lock so the per-minute Gemini quota isn't
    # hammered by parallel agents fanning out — onboarding fires 3-4 calls
    # in close succession and the free tier ratelimits at 10/min.
    global _last_call_ts
    async with _call_lock:
        now = time.monotonic()
        wait = _MIN_GAP_S - (now - _last_call_ts)
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            result = await _get_client().aio.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        finally:
            _last_call_ts = time.monotonic()
        return result


async def call_gemini(
    *,
    model: str,
    system: str,
    user_text: str,
    max_output_tokens: int = 2000,
    agent_name: str = "unknown",
    response_format: str = "text",  # "text" | "json"
) -> tuple[str, CostLedger]:
    settings = get_settings()
    # HARD kill switch: short-circuit to the stub BEFORE any API call — no spend.
    if kill_switch_on():
        log.warning("gemini.kill_switch — EMERGENCY_DISABLE_LLM on, stub (no spend)", agent=agent_name)
        return "[stub — EMERGENCY_DISABLE_LLM]", CostLedger(
            input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0
        )
    if not settings.gemini_api_key:
        log.warning("gemini.no_key — returning stub")
        return "[stub response — set GEMINI_API_KEY]", CostLedger(
            input_tokens=0, output_tokens=0, cached_tokens=0, cost_usd=0.0
        )

    ctx = current_run()
    effective_model = model
    if ctx and model in DEGRADE_MAP and await over_cap(ctx.tenant_id):
        effective_model = degrade_model(model)
        log.warning(
            "gemini.budget_degrade",
            tenant_id=ctx.tenant_id,
            from_model=model,
            to_model=effective_model,
        )
        try:
            from datetime import UTC, datetime

            await publish(
                ctx.user_id or "system",
                {
                    "type": "budget.exceeded",
                    "runId": ctx.run_id,
                    "spentUsd": settings.tenant_monthly_budget_usd,
                    "capUsd": settings.tenant_monthly_budget_usd,
                    "at": datetime.now(UTC).isoformat(),
                },
            )
        except Exception:  # noqa: BLE001
            log.exception("gemini.budget_publish_failed")

    # When the caller wants JSON we ask Gemini to emit a strict JSON MIME
    # type, which guarantees no markdown wrappers, no trailing commas, and
    # no commentary — the model is forced into JSON mode at the decoder.
    config_kwargs: dict[str, Any] = {
        "system_instruction": system,
        "max_output_tokens": max_output_tokens,
    }
    if response_format == "json":
        config_kwargs["response_mime_type"] = "application/json"
        # Disable "thinking" for structured extraction. Gemini 2.5 otherwise
        # spends the output-token budget reasoning and truncates the JSON
        # (parse errors: "Unterminated string" / "Expecting property name").
        # Guarded so older google-genai SDKs without ThinkingConfig still run.
        _thinking_cls = getattr(genai_types, "ThinkingConfig", None)
        if _thinking_cls is not None:
            config_kwargs["thinking_config"] = _thinking_cls(thinking_budget=0)

    # Inspector + Telegram timing — captured around _generate so retries inside
    # the tenacity wrapper roll into a single measurement (matches what the
    # Anthropic client does).
    started_at = time.monotonic()
    formatted_user_message = [{"role": "user", "content": user_text}]
    try:
        response = await _generate(
            model=effective_model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text=user_text)],
                )
            ],
            config=genai_types.GenerateContentConfig(**config_kwargs),
        )
    except Exception as exc:
        # AI Inspector — persist the failed call so the drawer shows users
        # exactly which prompt blew up (otherwise a Gemini error is silent in
        # the UI; only the structlog line records it).
        try:
            await record_llm_call(
                agent=agent_name,
                provider="gemini",
                model=effective_model,
                system_prompt=system,
                user_message=formatted_user_message,
                response_text="",
                latency_ms=int((time.monotonic() - started_at) * 1000),
                status="error",
                error_message=str(exc)[:500],
            )
        except Exception:  # noqa: BLE001
            log.exception("gemini.inspector_error_write_failed")
        raise

    in_tok = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
    out_tok = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
    ledger = CostLedger(
        input_tokens=in_tok,
        output_tokens=out_tok,
        cached_tokens=0,
        cost_usd=cost_usd(effective_model, in_tok, out_tok),
    )

    if ctx is not None:
        try:
            await record_token_usage(
                tenant_id=ctx.tenant_id,
                run_id=ctx.run_id,
                agent=agent_name,
                provider="gemini",
                model=effective_model,
                cost=ledger,
            )
        except Exception:  # noqa: BLE001
            log.exception("gemini.token_usage_write_failed")

    response_text = response.text or ""
    # AI Inspector — persist full prompt + response so the in-app drawer
    # shows the real Q/A (Gemini is the primary LLM now, so missing this
    # made the most-used model invisible in the Inspector).
    try:
        await record_llm_call(
            agent=agent_name,
            provider="gemini",
            model=effective_model,
            system_prompt=system,
            user_message=formatted_user_message,
            response_text=response_text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=ledger["cost_usd"],
            latency_ms=int((time.monotonic() - started_at) * 1000),
            status="ok",
        )
    except Exception:  # noqa: BLE001
        log.exception("gemini.inspector_write_failed")

    return response_text, ledger


async def grounded_search(
    query: str, *, max_results: int = 5, model: str = "gemini-2.5-flash"
) -> list[dict]:
    """Google-Search-grounded query → list of {title, url, snippet} pulled from
    Gemini's grounding metadata. Reuses GEMINI_API_KEY (no separate search key).

    Best-effort: returns [] when Gemini is unconfigured, the installed
    google-genai SDK lacks the GoogleSearch tool, or the call/parse fails — so
    the web_search primitive degrades cleanly to 'no results'.
    """
    settings = get_settings()
    if kill_switch_on():  # HARD kill switch — skip web search, no spend
        return []
    if not settings.gemini_api_key or not query.strip():
        return []
    search_cls = getattr(genai_types, "GoogleSearch", None)
    tool_cls = getattr(genai_types, "Tool", None)
    if not (search_cls and tool_cls):
        log.warning("gemini.grounding_unsupported — SDK has no GoogleSearch tool")
        return []

    try:
        response = await _generate(
            model=model,
            contents=[
                genai_types.Content(
                    role="user", parts=[genai_types.Part.from_text(text=query)]
                )
            ],
            # NOTE: cannot combine tools with response_mime_type=json — grounding
            # returns prose + citation chunks, which the caller then synthesises.
            config=genai_types.GenerateContentConfig(
                tools=[tool_cls(google_search=search_cls())],
                max_output_tokens=900,
            ),
        )
    except Exception as exc:  # noqa: BLE001 — grounding is best-effort
        log.warning("gemini.grounded_search_failed", error=str(exc)[:160])
        return []

    answer = (getattr(response, "text", None) or "").strip()
    out: list[dict] = []
    try:
        cand = (getattr(response, "candidates", None) or [None])[0]
        gm = getattr(cand, "grounding_metadata", None)
        chunks = getattr(gm, "grounding_chunks", None) or []
        for ch in chunks:
            web = getattr(ch, "web", None)
            uri = getattr(web, "uri", None) if web else None
            if not uri:
                continue
            out.append(
                {
                    "title": (getattr(web, "title", "") or "").strip(),
                    "url": uri,
                    "snippet": answer[:400],
                }
            )
            if len(out) >= max_results:
                break
    except Exception as exc:  # noqa: BLE001
        log.warning("gemini.grounded_parse_failed", error=str(exc)[:160])
    # If grounding produced an answer but exposed no citation chunks, still
    # surface the synthesised answer as a single result so the caller isn't blind.
    if not out and answer:
        out.append({"title": "Gemini web sintezi", "url": "", "snippet": answer[:400]})
    return out


async def analyze_media(
    *,
    image_url: str,
    question: str,
    model: str = "gemini-2.5-flash",
    agent_name: str = "vision",
    max_output_tokens: int = 700,
    json_mode: bool = False,
) -> str:
    """Vision: download an IG post cover/thumbnail and ask Gemini what it shows.

    This is how the voice coach "watches" a reel — instagrapi gives us the
    cover image + caption but no transcript, so we hand the cover to Gemini
    Flash (multimodal) and let it describe the content, style and topic.

    Best-effort: returns "" when Gemini isn't configured or the image can't be
    fetched, so callers fall back to caption-only understanding.
    """
    import httpx

    settings = get_settings()
    if kill_switch_on():  # HARD kill switch — skip vision, no spend
        return ""
    if not settings.gemini_api_key:
        log.warning("gemini.no_key — analyze_media skipped")
        return ""

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            img_bytes = resp.content
            mime = resp.headers.get("content-type", "image/jpeg").split(";")[0]
    except Exception as exc:  # noqa: BLE001
        log.warning("gemini.image_fetch_failed", error=str(exc)[:160])
        return ""

    # When the caller wants JSON back (e.g. post_analyzer's structured scoring),
    # force JSON MIME + disable thinking — otherwise Gemini 2.5 spends the output
    # budget reasoning and truncates the JSON mid-string, and emits unescaped
    # quotes inside values. Same guard call_gemini uses for its JSON path.
    cfg_kwargs: dict[str, Any] = {"max_output_tokens": max_output_tokens}
    if json_mode:
        cfg_kwargs["response_mime_type"] = "application/json"
        _thinking_cls = getattr(genai_types, "ThinkingConfig", None)
        if _thinking_cls is not None:
            cfg_kwargs["thinking_config"] = _thinking_cls(thinking_budget=0)

    started_at = time.monotonic()
    try:
        response = await _generate(
            model=model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[
                        genai_types.Part.from_bytes(data=img_bytes, mime_type=mime),
                        genai_types.Part.from_text(text=question),
                    ],
                )
            ],
            config=genai_types.GenerateContentConfig(**cfg_kwargs),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("gemini.vision_failed", error=str(exc)[:200])
        return ""

    text = response.text or ""
    in_tok = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
    out_tok = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
    ctx = current_run()
    with contextlib.suppress(Exception):
        await record_llm_call(
            agent=agent_name,
            provider="gemini",
            model=model,
            system_prompt="[vision] " + question,
            user_message=f"<image {len(img_bytes)} bytes {mime}>",
            response_text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost_usd(model, in_tok, out_tok),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            status="ok",
        )
    if ctx is not None:
        with contextlib.suppress(Exception):
            await record_token_usage(
                tenant_id=ctx.tenant_id,
                run_id=ctx.run_id,
                agent=agent_name,
                provider="gemini",
                model=model,
                cost=CostLedger(
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cached_tokens=0,
                    cost_usd=cost_usd(model, in_tok, out_tok),
                ),
            )
    return text


async def analyze_video(
    *,
    video_url: str,
    question: str,
    model: str = "gemini-2.5-flash",
    agent_name: str = "vision",
    max_output_tokens: int = 1000,
    json_mode: bool = False,
) -> str:
    """Vision over the ACTUAL reel — Gemini WATCHES the video (pacing, hook over
    time, transitions, retention risks), not just the static cover frame.

    Small reels (<18MB) go inline (fast); BIGGER videos now route through the Files API
    (analyze_video_file) instead of returning "" — so the coach can watch a full-length
    reference reel, not just short ones. Best-effort throughout.
    """
    import httpx

    settings = get_settings()
    if not settings.gemini_api_key:
        return ""
    if not video_url or not video_url.startswith("http"):
        return ""

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(video_url)
            resp.raise_for_status()
            vid = resp.content
            mime = resp.headers.get("content-type", "video/mp4").split(";")[0]
    except Exception as exc:  # noqa: BLE001
        log.warning("gemini.video_fetch_failed", error=str(exc)[:160])
        return ""

    if len(vid) <= 18 * 1024 * 1024:
        out = await analyze_video_bytes(
            video_bytes=vid, mime=mime, question=question, model=model,
            agent_name=agent_name, max_output_tokens=max_output_tokens, json_mode=json_mode,
        )
        if out:
            return out
    # Big video (or inline came back empty) → Files API: no 18MB cap, full-res understanding.
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".mp4" if "mp4" in mime else ".bin", delete=False) as tf:
            tf.write(vid)
            tmp = tf.name
        return await analyze_video_file(
            path=tmp, mime=mime, question=question, model=model,
            agent_name=agent_name, max_output_tokens=max_output_tokens, json_mode=json_mode,
        )
    finally:
        if tmp:
            with contextlib.suppress(OSError):
                os.unlink(tmp)


async def analyze_video_bytes(
    *,
    video_bytes: bytes,
    mime: str = "video/mp4",
    question: str,
    model: str = "gemini-2.5-flash",
    agent_name: str = "vision",
    max_output_tokens: int = 1000,
    json_mode: bool = False,
) -> str:
    """Vision over already-fetched video BYTES (e.g. a downscaled montage proxy the
    caller built locally — skips the httpx fetch `analyze_video` does). Inline upload
    caps at 18MB; bigger returns "". Best-effort; records the call if a RunContext is set."""
    settings = get_settings()
    if not settings.gemini_api_key:
        return ""
    if not mime.startswith("video") or len(video_bytes) > 18 * 1024 * 1024:
        return ""  # not a video / too big for inline upload

    cfg_kwargs: dict[str, Any] = {"max_output_tokens": max_output_tokens}
    if json_mode:
        cfg_kwargs["response_mime_type"] = "application/json"
        _thinking_cls = getattr(genai_types, "ThinkingConfig", None)
        if _thinking_cls is not None:
            cfg_kwargs["thinking_config"] = _thinking_cls(thinking_budget=0)

    started_at = time.monotonic()
    try:
        response = await _generate(
            model=model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[
                        genai_types.Part.from_bytes(data=video_bytes, mime_type=mime),
                        genai_types.Part.from_text(text=question),
                    ],
                )
            ],
            config=genai_types.GenerateContentConfig(**cfg_kwargs),
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("gemini.video_failed", error=str(exc)[:200])
        with contextlib.suppress(Exception):  # surface the failed call in the Inspector
            await record_llm_call(
                agent=agent_name,
                provider="gemini",
                model=model,
                system_prompt="[video] " + question,
                user_message=f"<video {len(video_bytes)} bytes {mime}>",
                response_text="",
                latency_ms=int((time.monotonic() - started_at) * 1000),
                status="error",
                error_message=str(exc)[:500],
            )
        return ""

    text = response.text or ""
    in_tok = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
    out_tok = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
    ctx = current_run()
    with contextlib.suppress(Exception):
        await record_llm_call(
            agent=agent_name,
            provider="gemini",
            model=model,
            system_prompt="[video] " + question,
            user_message=f"<video {len(video_bytes)} bytes {mime}>",
            response_text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost_usd(model, in_tok, out_tok),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            status="ok",
        )
    if ctx is not None:
        with contextlib.suppress(Exception):
            await record_token_usage(
                tenant_id=ctx.tenant_id,
                run_id=ctx.run_id,
                agent=agent_name,
                provider="gemini",
                model=model,
                cost=CostLedger(
                    input_tokens=in_tok,
                    output_tokens=out_tok,
                    cached_tokens=0,
                    cost_usd=cost_usd(model, in_tok, out_tok),
                ),
            )
    return text


def _file_state(f: Any) -> str:
    """FileState enum → its name ('ACTIVE' | 'PROCESSING' | 'FAILED' | ...), str-safe."""
    st = getattr(f, "state", None)
    return getattr(st, "name", str(st)) if st is not None else "STATE_UNSPECIFIED"


async def _record_video_call(
    agent_name: str, model: str, question: str, label: str,
    text: str, in_tok: int, out_tok: int, started_at: float, status: str, err: str | None,
) -> None:
    """AI Inspector + token-usage for a Files-API video call (RunContext billing if set)."""
    with contextlib.suppress(Exception):
        await record_llm_call(
            agent=agent_name, provider="gemini", model=model,
            system_prompt="[video-file] " + question,
            user_message=f"<video file {label}>",
            response_text=text, input_tokens=in_tok, output_tokens=out_tok,
            cost_usd=cost_usd(model, in_tok, out_tok),
            latency_ms=int((time.monotonic() - started_at) * 1000),
            status=status, error_message=err,
        )
    ctx = current_run()
    if ctx is not None and status == "ok":
        with contextlib.suppress(Exception):
            await record_token_usage(
                tenant_id=ctx.tenant_id, run_id=ctx.run_id, agent=agent_name,
                provider="gemini", model=model,
                cost=CostLedger(input_tokens=in_tok, output_tokens=out_tok, cached_tokens=0,
                                cost_usd=cost_usd(model, in_tok, out_tok)),
            )


async def analyze_video_file(
    *,
    path: str,
    mime: str = "video/mp4",
    question: str,
    model: str = "gemini-2.5-flash",
    agent_name: str = "vision",
    max_output_tokens: int = 4000,
    json_mode: bool = False,
    poll_timeout_s: float = 150.0,
) -> str:
    """DEEP video understanding via the Gemini Files API — uploads the clip (NO 18MB inline cap,
    so full-res + AUDIO + longer videos), waits until it's processed server-side, asks Gemini,
    then deletes the file. This is how we read on-screen text, fine effects and pacing that the
    360p/8fps inline proxy can't show. Degrade-safe: returns "" on ANY failure so the caller
    falls back to the inline path."""
    settings = get_settings()
    if not settings.gemini_api_key or not path:
        return ""  # a missing/unreadable path raises on upload below → caught → ""
    client = _get_client()
    started_at = time.monotonic()
    file_name: str | None = None
    try:
        uploaded = await client.aio.files.upload(
            file=path, config=genai_types.UploadFileConfig(mime_type=mime)
        )
        file_name = uploaded.name
        if not file_name:
            raise RuntimeError("gemini upload returned no file name")
        # Video needs server-side processing before it's queryable — poll until ACTIVE.
        f = uploaded
        deadline = time.monotonic() + poll_timeout_s
        while _file_state(f) == "PROCESSING":
            if time.monotonic() > deadline:
                raise TimeoutError("gemini files processing timeout")
            await asyncio.sleep(2.0)
            f = await client.aio.files.get(name=file_name)
        if _file_state(f) != "ACTIVE":
            raise RuntimeError(f"gemini file not active: {_file_state(f)}")
        uri = f.uri
        if not uri:
            raise RuntimeError("gemini file has no uri")

        cfg_kwargs: dict[str, Any] = {"max_output_tokens": max_output_tokens}
        if json_mode:
            cfg_kwargs["response_mime_type"] = "application/json"
            _thinking_cls = getattr(genai_types, "ThinkingConfig", None)
            if _thinking_cls is not None:
                cfg_kwargs["thinking_config"] = _thinking_cls(thinking_budget=0)

        response = await _generate(
            model=model,
            contents=[
                genai_types.Content(
                    role="user",
                    parts=[
                        genai_types.Part.from_uri(file_uri=uri, mime_type=f.mime_type or mime),
                        genai_types.Part.from_text(text=question),
                    ],
                )
            ],
            config=genai_types.GenerateContentConfig(**cfg_kwargs),
        )
        text = response.text or ""
        in_tok = getattr(response.usage_metadata, "prompt_token_count", 0) or 0
        out_tok = getattr(response.usage_metadata, "candidates_token_count", 0) or 0
        await _record_video_call(
            agent_name, model, question, os.path.basename(path), text, in_tok, out_tok, started_at, "ok", None
        )
        return text
    except Exception as exc:  # noqa: BLE001 — deep vision is best-effort; caller falls back
        log.warning("gemini.video_file_failed", error=str(exc)[:200])
        await _record_video_call(
            agent_name, model, question, os.path.basename(path), "", 0, 0, started_at, "error", str(exc)[:500]
        )
        return ""
    finally:
        if file_name:
            with contextlib.suppress(Exception):
                await client.aio.files.delete(name=file_name)
