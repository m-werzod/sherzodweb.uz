# SMM Coach — Activation Guide (external resources → live features)

Everything below is **already coded, deployed, and verified**. Each item is a
one-time setup on your side that *activates* shipped-but-dormant code. Set env
vars in **Coolify → smm-coach → Environment**, then redeploy (Coolify API per
`~/.claude/.../coolify-deploy-trigger` memory, or the UI Deploy button).

After setting any of these, tell Claude — it will verify the feature end-to-end
on prod (SSH + a live call).

---

## 1. Web search — sharper Stage 3a/3b (competitor + trend grounding)
- **Status:** ALREADY WORKING via the existing `GEMINI_API_KEY` (Gemini
  google_search grounding). Verified live: a niche query returned real results.
- **To upgrade quality:** set **`TAVILY_API_KEY`** (https://tavily.com, free tier).
  `web_search()` prefers Tavily (cleaner structured results) and falls back to
  Gemini automatically. No redeploy of logic needed — just the env var + restart.
- **Lights up:** industry_news, competitor_intel (auto-discovery), market_analyst,
  `knowledge_refresher` daily cache.
- **Verify:** Claude runs `web_search("<niche> Instagram trend uz 2026")` in the
  agents container → expects ≥1 result with a real URL.

## 2. Real competitor / trend / exemplar DATA — Stage 3a/3b/5/13
- Set **`IG_SCRAPER_ACCOUNTS`** (JSON: 2–3 throwaway IG logins) +
  **`IG_SCRAPER_PROXY_URL`** (residential proxy, e.g. Smartproxy ~$10–20/mo).
- **Lights up:** competitor_tracker writes real `competitor_snapshot` rows;
  market_analyst live hashtag scrape; shared_knowledge exemplar posts (→ forecast
  exemplar grounding); private-account fallback.
- **Verify:** Claude triggers a competitor scrape + checks `shared_knowledge` rows.

## 3. Background music bedding — Stage 9c
- Drop a few **CC0 `.mp3` files** into `apps/agents/app/assets/music/` (committed
  to the repo, so they ship in the agents image) + a **`manifest.json`** mapping
  each file → `{ "energy": 0.0-1.0, "mood": "...", "bpm": N }`.
- **Lights up:** `pick_track` (energy-aware) → the montage compiler beds music
  under the voice (sidechain-ducked, already in the filtergraph). Without files,
  renders are voice-only (dormant, not broken).
- **Verify:** Claude renders a montage on prod → confirms a music bed track is
  selected + ducked.

## 4. Lead DMs — Stage 12 Faza 2
- Submit **Meta App Review** for `instagram_business_manage_messages` (2–6 weeks;
  only needed for DMing leads / multi-user — the single-person MVP's comment
  replies + publish already work on Standard Access).
- **Lights up:** DM-to-lead from the `/leads` inbox (the lead detection, inbox,
  and drafted replies are already live).

## 5. AI music generation — Stage 9c (central vision promise)
- Provide a **Suno / fal.ai / MusicGen API key** (and tell Claude which).
- Claude will then build the flag-gated music-gen agent (it's the one piece left
  unbuilt because it needs a provider choice + key).

---

## Operational env (for autonomous scheduling/publish to actually fire)
These gate the workers that drive auto-publish + the daily sweeps:
- **`RUN_WORKERS=1`** on both agents services (brain + media planes) — confirmed set.
- **`WEB_URL`** + **`CRON_SECRET`** — let the agents workers call the web cron
  routes (`/api/cron/publish-due`, `/api/cron/autoqueue`). Without them,
  ScheduledPosts sit pending and cadence auto-queue never fires.
- **`autoSchedule`** is a per-user opt-in toggle in Settings (default OFF) — it
  must be turned on by the user for cadence auto-queue to schedule anything.

## What needs no action (already live + verified in prod)
Stages 1 (OCEAN+archetypes), 2 (Graph-snapshot+reel-speech), 4 (goal KPI+stations),
5 (forecast+calibration), 6 (universal vault+dedup+telemetry+refresher), 7
(scriptwriter depth+re-ask), 9b (semantic cut + render critique + effect fallback),
11 (best-time), 12 (lead funnel + inbox), 13 (self-correction loop), 14 (voice
tools). ~67% MVP; the remaining % is the external items above + the XL agent-fleet
expansion (needs a product spec of which new specialist agents to add).
