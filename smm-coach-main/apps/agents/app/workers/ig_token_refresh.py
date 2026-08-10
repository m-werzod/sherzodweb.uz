"""Monitor IG long-lived token expiry.

Long-lived IG tokens are valid for 60 days. This worker:
1. Lists accounts whose token expires within 7 days
2. Decrypts the stored token (AES-256-GCM via HKDF from AUTH_SECRET)
3. Calls Instagram's refresh_access_token endpoint
4. Re-encrypts the new token and updates the DB

Daily tick at 02:00 UTC.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import httpx
import structlog
from sqlalchemy import text

from app.integrations import telegram
from app.memory.db import get_sessionmaker
from app.security.crypto import decrypt_token, encrypt_token

log = structlog.get_logger(__name__)

TICK_INTERVAL_SEC = 24 * 60 * 60  # daily
REFRESH_WINDOW_DAYS = 7
GRAPH_REFRESH_URL = "https://graph.instagram.com/refresh_access_token"


async def _refresh_token(access_token: str) -> dict | None:
    """Call Instagram's token refresh endpoint. Returns new token data or None."""
    params = {
        "grant_type": "ig_refresh_token",
        "access_token": access_token,
    }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.get(GRAPH_REFRESH_URL, params=params)
            r.raise_for_status()
            data = r.json()
            return {
                "access_token": data.get("access_token"),
                "expires_in": data.get("expires_in"),
            }
    except Exception as exc:  # noqa: BLE001
        log.warning("ig_token_refresh.api_failed", error=str(exc)[:200])
        return None


async def _retire_expired(sm: object, now: datetime) -> int:
    """Retire accounts whose token has ALREADY expired. Instagram's ig_refresh_token only works on a
    still-valid token, so attempting to refresh a dead one failed every single day forever and the
    account was never flagged. Here we mark it for reconnect (verified=false), null the dead access
    token so nothing tries to use it, and alert ONCE — the `verified = true` guard makes a row
    eligible only on the first expired tick, so after retiring it's excluded (throttled)."""
    async with sm() as session:  # type: ignore[operator]
        res = await session.execute(
            text(
                """
                UPDATE instagram_accounts
                SET verified = false, "oauthAccessTokenEnc" = NULL, "updatedAt" = NOW()
                WHERE "oauthExpiresAt" IS NOT NULL
                  AND "oauthExpiresAt" < :now
                  AND "oauthAccessTokenEnc" IS NOT NULL
                  AND verified = true
                RETURNING id, "tenantId"
                """
            ),
            {"now": now},
        )
        rows = res.mappings().all()
        await session.commit()
    for r in rows:
        log.info("ig_token_refresh.retired_expired", account_id=r["id"], tenant_id=r["tenantId"])
    if rows:
        telegram.send(
            f"⚠️ IG token muddati tugadi · {len(rows)} ta akkaunt qayta ulanishi kerak (reconnect)"
        )
    return len(rows)


async def _tick() -> tuple[int, int]:
    """Refresh expiring tokens. Returns (attempted, succeeded)."""
    sm = get_sessionmaker()
    now = datetime.utcnow()
    cutoff = now + timedelta(days=REFRESH_WINDOW_DAYS)
    # First retire already-dead tokens (see _retire_expired), then refresh only the ones still in the
    # VALID window (> now): a token past expiry can't be refreshed, so it must never enter the loop.
    await _retire_expired(sm, now)
    async with sm() as session:
        result = await session.execute(
            text(
                """
                SELECT id, "tenantId", "oauthAccessTokenEnc", "oauthRefreshTokenEnc"
                FROM instagram_accounts
                WHERE "oauthExpiresAt" IS NOT NULL
                  AND "oauthExpiresAt" > :now
                  AND "oauthExpiresAt" < :cutoff
                  AND "oauthAccessTokenEnc" IS NOT NULL
                """
            ),
            {"now": now, "cutoff": cutoff},
        )
        rows = result.mappings().all()

    attempted = len(rows)
    succeeded = 0

    for row in rows:
        account_id = row["id"]
        tenant_id = row["tenantId"]
        enc_access = row["oauthAccessTokenEnc"]
        enc_refresh = row["oauthRefreshTokenEnc"]

        # Prefer refresh token if available; fall back to access token
        token_to_refresh = None
        if enc_refresh:
            try:
                token_to_refresh = decrypt_token(enc_refresh)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "ig_token_refresh.decrypt_refresh_failed",
                    account_id=account_id,
                    error=str(exc)[:120],
                )
        if not token_to_refresh and enc_access:
            try:
                token_to_refresh = decrypt_token(enc_access)
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "ig_token_refresh.decrypt_access_failed",
                    account_id=account_id,
                    error=str(exc)[:120],
                )

        if not token_to_refresh:
            log.warning(
                "ig_token_refresh.no_decryptable_token",
                account_id=account_id,
            )
            continue

        refreshed = await _refresh_token(token_to_refresh)
        if not refreshed or not refreshed.get("access_token"):
            log.warning(
                "ig_token_refresh.api_returned_empty",
                account_id=account_id,
            )
            continue

        new_token = refreshed["access_token"]
        expires_in = refreshed.get("expires_in", 5184000)  # default 60 days
        new_expires = datetime.utcnow() + timedelta(seconds=expires_in)

        # Re-encrypt
        try:
            new_enc_access = encrypt_token(new_token)
        except Exception as exc:  # noqa: BLE001
            log.error(
                "ig_token_refresh.encrypt_failed",
                account_id=account_id,
                error=str(exc)[:120],
            )
            continue

        # Update DB
        async with sm() as session:
            await session.execute(
                text(
                    """
                    UPDATE instagram_accounts
                    SET "oauthAccessTokenEnc" = :enc,
                        "oauthExpiresAt" = :expires,
                        "updatedAt" = NOW()
                    WHERE id = :id
                    """
                ),
                {
                    "id": account_id,
                    "enc": new_enc_access,
                    "expires": new_expires,
                },
            )
            await session.commit()

        succeeded += 1
        log.info(
            "ig_token_refresh.success",
            account_id=account_id,
            tenant_id=tenant_id,
            new_expires=new_expires.isoformat(),
        )

    return attempted, succeeded


async def run_forever() -> None:
    log.info("ig_token_refresh.start", interval_sec=TICK_INTERVAL_SEC)
    while True:
        try:
            attempted, succeeded = await _tick()
            if attempted > 0:
                msg = (
                    f"🔑 IG token refresh · {succeeded}/{attempted} ta akkaunt "
                    f"yangilandi ({REFRESH_WINDOW_DAYS} kun ichida tugaydiganlar)"
                )
                log.info("ig_token_refresh.batch_done", attempted=attempted, succeeded=succeeded)
                telegram.send(msg)
        except Exception:  # noqa: BLE001
            log.exception("ig_token_refresh.tick_failed")
        await asyncio.sleep(TICK_INTERVAL_SEC)


if __name__ == "__main__":
    asyncio.run(run_forever())
