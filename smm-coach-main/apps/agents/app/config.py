"""Application configuration loaded from environment."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env.local", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # An empty shell variable should NOT mask the value in the .env file.
        # Without this, `ANTHROPIC_API_KEY=` exported by some prior shell
        # command silently disables real LLM calls.
        env_ignore_empty=True,
    )

    env: Literal["development", "production", "test"] = Field(
        default="development", alias="NODE_ENV"
    )
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # --- Database ---------------------------------------------------------
    database_url: str = Field(alias="DATABASE_URL")
    direct_url: str | None = Field(default=None, alias="DIRECT_URL")
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")

    # --- LLM providers ----------------------------------------------------
    anthropic_api_key: SecretStr | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    gemini_api_key: SecretStr | None = Field(default=None, alias="GEMINI_API_KEY")
    openai_api_key: SecretStr | None = Field(default=None, alias="OPENAI_API_KEY")
    groq_api_key: SecretStr | None = Field(default=None, alias="GROQ_API_KEY")
    cerebras_api_key: SecretStr | None = Field(default=None, alias="CEREBRAS_API_KEY")
    openrouter_api_key: SecretStr | None = Field(default=None, alias="OPENROUTER_API_KEY")
    # Stock B-roll (Faza 3) — Pexels free video API; absent → b-roll silently skipped.
    pexels_api_key: SecretStr | None = Field(default=None, alias="PEXELS_API_KEY")
    # Faza B (GPU plane): generative B-roll via fal.ai. Unset → generation inert, montage uses stock.
    fal_key: SecretStr | None = Field(default=None, alias="FAL_KEY")
    fal_video_model: str = Field(
        default="fal-ai/kling-video/v1/standard/text-to-video", alias="FAL_VIDEO_MODEL"
    )
    # Opt-in cinematic: when set (and FAL_KEY present) broll_curator marks missing-footage shots
    # source=generate so they are AI-generated instead of stock. Off by default (cost + needs verify).
    enable_gen_broll: bool = Field(default=False, alias="ENABLE_GEN_BROLL")
    # Faza D: video object-removal (inpaint) via fal void-video-inpainting. Runs only when a task
    # carries an inpaint-remove instruction AND this is on AND FAL_KEY is set. Off by default (cost).
    fal_inpaint_model: str = Field(default="fal-ai/void-video-inpainting", alias="FAL_INPAINT_MODEL")
    enable_inpaint: bool = Field(default=False, alias="ENABLE_INPAINT")
    # Faza C: scenario-matched decor/background — bria matte (subject cut-out) + FLUX generated bg.
    # Runs when a task carries a decor instruction AND this is on AND FAL_KEY is set. Off by default.
    fal_matte_model: str = Field(default="bria/video/background-removal", alias="FAL_MATTE_MODEL")
    fal_image_model: str = Field(default="fal-ai/flux/schnell", alias="FAL_IMAGE_MODEL")
    enable_decor: bool = Field(default=False, alias="ENABLE_DECOR")

    # --- Higgsfield (cinematic per-shot AI video — separate opt-in pipeline) ---
    # Scenario storyboard → per-shot image→video via Higgsfield DoP (one keyframe image +
    # prompt + optional camera-motion preset → ~5s cinematic clip). Our own assembler then concats
    # the per-shot clips + burns captions (from scriptTimeline) + beds music. Higgsfield takes NO
    # audio/music and NO whole-video input, so music + assembly stay on our side. Every path is
    # FAIL-SOFT: no creds / API error / a failed shot → that shot is skipped and assembly uses
    # whatever succeeded. Off by default (paid service + per-clip cost).
    #
    # Auth REUSES the web lib/higgsfield V2 scheme ("Authorization: Key <ID>:<SECRET>") so the SAME
    # account credentials power both surfaces — no new key needed. Resolved from HF_CREDENTIALS
    # ("ID:SECRET", split on first ':') OR HF_API_KEY + HF_API_SECRET. Endpoint POST {base}
    # /v1/image2video/dop, poll GET {base}/requests/{id}/status (mirrors apps/web/src/lib/higgsfield).
    hf_credentials: SecretStr | None = Field(default=None, alias="HF_CREDENTIALS")
    hf_api_key: str | None = Field(default=None, alias="HF_API_KEY")
    hf_api_secret: SecretStr | None = Field(default=None, alias="HF_API_SECRET")
    higgsfield_base_url: str = Field(
        default="https://platform.higgsfield.ai", alias="HIGGSFIELD_BASE_URL"
    )
    # DoP quality tier: dop-lite (fast/cheap) | dop-turbo | dop-standard (best).
    higgsfield_video_model: str = Field(default="dop-turbo", alias="HIGGSFIELD_VIDEO_MODEL")
    # Keyframe image generator for shots with no usable footage frame (fal FLUX; needs FAL_KEY).
    higgsfield_image_model: str = Field(default="fal-ai/flux/schnell", alias="HIGGSFIELD_IMAGE_MODEL")
    # Camera-motion presets are Higgsfield motion UUIDs. We can't hardcode them, so the director
    # picks a NEUTRAL motion NAME ("push_in", "orbit", …) and this JSON maps name→id. Empty → no
    # motion sent (the camera move still rides in the prompt text). Paste ids from Higgsfield docs.
    #   e.g. HIGGSFIELD_MOTION_CATALOG={"orbit":"c5881721-...","push_in":"...","static":"..."}
    higgsfield_motion_catalog: str = Field(default="", alias="HIGGSFIELD_MOTION_CATALOG")
    enable_higgsfield: bool = Field(default=False, alias="ENABLE_HIGGSFIELD")

    # --- Runway (video-to-video RESTYLE of an uploaded clip) --------------
    # Higgsfield's API can't take a video as input; Runway Aleph CAN — it edits/restyles an existing
    # clip from a text prompt (verified live against api.dev.runwayml.com). Flow:
    #   POST {base}/v1/video_to_video  headers Authorization: Bearer <key> + X-Runway-Version: <ver>
    #     body {"model","videoUri"(PUBLIC url),"promptText","ratio"} → {"id"}
    #   poll GET {base}/v1/tasks/{id} → {"status":"...","output":["https://...mp4"]}
    # Off by default (paid — per-second credits, ~20s/call). Uses the SAME RUNWAY_API_KEY already set.
    runway_api_key: SecretStr | None = Field(default=None, alias="RUNWAY_API_KEY")
    runway_api_base: str = Field(default="https://api.dev.runwayml.com", alias="RUNWAY_API_BASE")
    runway_api_version: str = Field(default="2024-11-06", alias="RUNWAY_API_VERSION")
    # Video-to-video model: gen4_aleph | aleph2 (restyle) — see the live /v1/video_to_video enum.
    runway_video_model: str = Field(default="gen4_aleph", alias="RUNWAY_VIDEO_MODEL")
    runway_ratio: str = Field(default="720:1280", alias="RUNWAY_RATIO")  # 9:16 vertical
    enable_runway_restyle: bool = Field(default=False, alias="ENABLE_RUNWAY_RESTYLE")

    # --- Shotstack (cloud RENDER plane — MONTAGE-PRO F1) -------------------
    # The EDL brain stays in-house; the polish render is delegated to Shotstack's Edit API
    # (cuts→clips, ken-burns→zoom effects, karaoke captions via SRT — language-unlimited, music,
    # b-roll). FAIL-SOFT: any cloud error falls back to the local ffmpeg degrade ladder, so a
    # render always completes. `stage` env renders watermarked sandbox output for free POCs.
    shotstack_api_key: SecretStr | None = Field(default=None, alias="SHOTSTACK_API_KEY")
    shotstack_env: Literal["stage", "v1"] = Field(default="stage", alias="SHOTSTACK_ENV")
    enable_shotstack: bool = Field(default=False, alias="ENABLE_SHOTSTACK")

    # Best-of-breed routing. Each node picks the provider whose strength
    # matches the task; soft-fallback chain lets the system degrade gracefully
    # if any single key is missing.
    #
    #   Creative scriptwriter ........ Opus 4 → Gemini 2.5 Pro
    #   Critique / polish ............ Sonnet 4.6 (instruction following)
    #   Strict JSON validators ....... Haiku 4.5 (lowest hallucination)
    #   Web-grounded research ........ Gemini 2.5 Flash (native Google search)
    #   Long-context bulk reading .... Gemini 2.5 Flash (1M context)
    #   Fast classification (volume) . Cerebras/OpenRouter Llama 3.3 70B (Haiku fallback)
    #   Vision .................. .... Gemini 2.5 Flash (best multimodal)
    #   Weekly market synthesis ...... Sonnet 4.6 (nuanced writing)
    #   Embeddings ................... Gemini text-embedding-004 (FREE)
    model_scriptwriter_primary: str = "claude-opus-4-7"
    model_scriptwriter_revise: str = "claude-sonnet-4-6"
    model_initial_analysis: str = "claude-sonnet-4-6"
    model_roadmap_generator: str = "claude-sonnet-4-6"
    model_drift_detector: str = "claude-haiku-4-5"
    model_output_validator: str = "claude-haiku-4-5"
    model_vault_seeder: str = "claude-haiku-4-5"  # niche-foundation vault seeding
    # Cerebras / OpenRouter — fast, cheap, OpenAI-compatible. Default engine for
    # the high-volume agent tasks (scoring, enrichment, market/industry synthesis).
    # fast_llm tries each configured provider in turn (Cerebras → OpenRouter by
    # default; flip with LLM_FAST_PROVIDER=openrouter) and only falls back to
    # Claude Haiku when ALL fast providers fail. Both model ids are env-tunable
    # so a billing-blocked provider can be swapped without a code change.
    # The deployed Cerebras key serves gpt-oss-120b (Production, 1000 RPM /
    # 1M TPM) + zai-glm-4.7 (Preview) — NOT llama-3.3-70b (which 404s). Use the
    # Production model; override per-deploy via CEREBRAS_MODEL.
    model_fast: str = Field(default="gpt-oss-120b", alias="CEREBRAS_MODEL")
    model_fast_openrouter: str = Field(
        default="meta-llama/llama-3.3-70b-instruct", alias="OPENROUTER_MODEL"
    )
    # Adversarial critic — Gemini Flash is right-sized: cheap (~$0.02/task),
    # fast (response in <5s), and 1M context handles any script the
    # scriptwriter emits. We never want Opus here because the critic is
    # called on EVERY script generation; doubling its cost would make
    # quality gating economically unviable.
    model_adversarial_critic: str = "gemini-2.5-flash"
    model_industry_news: str = "gemini-2.5-flash"
    # Routed through groq_client → fast_llm (Cerebras/OpenRouter), Haiku fallback.
    # The id here is a display/label default; fast_llm uses each provider's own
    # model (model_fast / model_fast_openrouter), so it stays provider-neutral.
    model_account_tracker: str = "llama-3.3-70b"
    model_market_analyst: str = "gemini-2.5-flash"
    model_market_synthesis: str = "claude-sonnet-4-6"
    model_vision: str = "gemini-2.5-flash"
    model_embeddings: str = "voyage-3"
    embeddings_dim: int = 1024  # voyage-3 native dim

    # --- Instagram scraping ----------------------------------------------
    ig_scraper_accounts: str | None = Field(default=None, alias="IG_SCRAPER_ACCOUNTS")
    ig_scraper_proxy_url: str | None = Field(default=None, alias="IG_SCRAPER_PROXY_URL")

    # --- Embeddings ------------------------------------------------------
    voyage_api_key: SecretStr | None = Field(default=None, alias="VOYAGE_API_KEY")

    # --- Web search (Stage 3a/3b grounding) -------------------------------
    # Tavily is the preferred provider (clean structured results). When unset,
    # web_search falls back to Gemini google_search grounding (reuses
    # GEMINI_API_KEY), so live grounding works even before a Tavily key arrives.
    tavily_api_key: SecretStr | None = Field(default=None, alias="TAVILY_API_KEY")

    # --- Instagram --------------------------------------------------------
    instagram_app_id: str | None = Field(default=None, alias="INSTAGRAM_APP_ID")
    instagram_app_secret: SecretStr | None = Field(
        default=None, alias="INSTAGRAM_APP_SECRET"
    )

    # --- Observability ----------------------------------------------------
    langfuse_public_key: SecretStr | None = Field(default=None, alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: SecretStr | None = Field(default=None, alias="LANGFUSE_SECRET_KEY")
    langfuse_host: str | None = Field(default=None, alias="LANGFUSE_HOST")
    sentry_dsn: str | None = Field(default=None, alias="SENTRY_DSN")

    # --- Inter-service security ------------------------------------------
    agents_hmac_secret: SecretStr = Field(alias="AGENTS_HMAC_SECRET")

    # --- Budgets ----------------------------------------------------------
    # Three-layer LLM spend caps. When any trips, premium models (Opus,
    # Gemini Pro) are silently swapped for cheap fallbacks (Haiku, Flash);
    # the user keeps getting responses, just not premium-tier ones.
    #
    #   tenant_monthly  → per-tenant per calendar month  (~30 tasks)
    #   tenant_daily    → per-tenant per rolling 24h     (loop safety net)
    #   global_daily    → total spend across all tenants (single bug fuse)
    #
    # All can be disabled by setting to 0. Override via env vars
    # TENANT_MONTHLY_BUDGET_USD / TENANT_DAILY_BUDGET_USD / GLOBAL_DAILY_BUDGET_USD.
    #
    # Hard kill-switch: EMERGENCY_DISABLE_LLM=1 → every LLM COMPLETION / vision /
    # web-search call short-circuits to a stub at the client layer (kill_switch_on),
    # so no money is spent on the agent loop regardless of bugs/loops. (Distinct
    # from the soft per-tenant/global caps, which only DEGRADE premium→cheap.)
    # Voyage embeddings — negligible cost + needed for retrieval stubs — still run.
    tenant_monthly_budget_usd: float = Field(default=20.0, alias="TENANT_MONTHLY_BUDGET_USD")
    tenant_daily_budget_usd: float = Field(default=3.0, alias="TENANT_DAILY_BUDGET_USD")
    global_daily_budget_usd: float = Field(default=15.0, alias="GLOBAL_DAILY_BUDGET_USD")
    # Tracking-only mode: when False, spend is STILL recorded (the AI-spend panel keeps counting)
    # but the caps never degrade models — full premium quality, no limit. Set BUDGET_ENFORCE=false
    # while testing; flip back to true before launch so the caps protect against runaway cost.
    budget_enforce: bool = Field(default=True, alias="BUDGET_ENFORCE")

    # --- Feature flags ----------------------------------------------------
    enable_heygen_avatar: bool = Field(default=False, alias="ENABLE_HEYGEN_AVATAR")
    enable_auto_publish: bool = Field(default=False, alias="ENABLE_AUTO_PUBLISH")
    # HeyGen Video Translation (lokalizatsiya): user reelini N-tilga lip-sync dublyaj → EDL
    # lang_variants. Opt-in: bu YOQILGAN + HEYGEN_API_KEY + bir til so'ralganda ishlaydi. Default off.
    enable_video_translate: bool = Field(default=False, alias="ENABLE_VIDEO_TRANSLATE")
    # Vergul-ajratilgan default til ro'yxati (masalan "ru,en"); task meta `translateLangs` ustun keladi.
    video_translate_langs: str = Field(default="", alias="VIDEO_TRANSLATE_LANGS")

    # --- Media / video gen keys -----------------------------------------
    heygen_api_key: SecretStr | None = Field(default=None, alias="HEYGEN_API_KEY")
    heygen_default_avatar_id: str | None = Field(default=None, alias="HEYGEN_DEFAULT_AVATAR_ID")
    runway_api_key: SecretStr | None = Field(default=None, alias="RUNWAY_API_KEY")
    elevenlabs_api_key: SecretStr | None = Field(default=None, alias="ELEVENLABS_API_KEY")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
