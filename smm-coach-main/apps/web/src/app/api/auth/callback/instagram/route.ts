/**
 * GET /api/auth/callback/instagram
 *
 * Meta redirects the user here after they grant (or deny) the OAuth
 * dialog. Two modes (selected by the `ig_oauth_mode` cookie set in
 * /api/auth/instagram/start):
 *
 *   1. `connect` — there is an Auth.js session; link IG to current user.
 *   2. `signin`  — no session; either find a User by
 *                  InstagramAccount.instagramUserId and sign them in,
 *                  or create a fresh User + Tenant and sign them in.
 *
 * Shared steps:
 *   • verify CSRF state
 *   • exchange code → short-lived → long-lived (60d) token
 *   • fetch /me profile
 *   • mirror avatar + media thumbnails into MinIO so the UI keeps
 *     working after IG's CDN tokens expire
 *   • upsert InstagramAccount with encrypted token
 *   • seed instagram_posts (capped at 50)
 *   • for `signin`: forge an Auth.js JWT cookie so the user lands
 *     authenticated
 */
import { NextResponse } from 'next/server';
import { cookies } from 'next/headers';
import { encode } from 'next-auth/jwt';
import { auth } from '@/lib/auth/auth';
import { prisma, prismaForTenant } from '@smm/db';
import { encryptToken } from '@/lib/security/crypto';
import {
  exchangeCode,
  exchangeLongLived,
  fetchProfile,
  REQUIRED_SCOPES,
} from '@/lib/instagram/graph-api-client';
import { mirrorInstagramAsset } from '@/lib/instagram/media-mirror';
import { syncInstagramAccount } from '@/lib/instagram/sync-account';
import { ensureFreeSubscription } from '@/lib/payments/subscription';
import { dispatchProfileAudit } from '@/lib/instagram/audit-dispatch';
import { notifyTelegram } from '@/lib/telegram';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

/**
 * Next.js standalone binds the Node server to 0.0.0.0 — `req.url` then
 * reports the bind address, not the public host (Traefik forwards the
 * `Host` header but Next.js doesn't auto-rewrite `request.url`). Build
 * every outbound redirect off NEXTAUTH_URL so the browser lands on the
 * real domain.
 */
function publicBase(reqUrl: URL): string {
  return process.env.NEXTAUTH_URL || reqUrl.origin;
}

function back(reqUrl: URL, target: string, params: Record<string, string>): Response {
  const url = new URL(target, publicBase(reqUrl));
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  return NextResponse.redirect(url);
}

/**
 * Pick where to send the user on OAuth failure. Original behaviour always
 * routed to /sign-in, which logged out anyone who clicked "Connect" while
 * already authenticated. Now: if a session exists, bounce back to the
 * dashboard with an inline error param instead of nuking the session.
 *
 * Optional `detail` carries Meta's raw error message (truncated) so the
 * banner can show "Invalid platform app" or "redirect_uri does not match
 * Valid Redirect URIs" instead of a generic code.
 */
function errorBack(
  reqUrl: URL,
  isLoggedIn: boolean,
  igError: string,
  detail?: string,
  loggedInReturn = '/dashboard',
): Response {
  const params: Record<string, string> = { ig_error: igError };
  if (detail) params.ig_detail = detail.slice(0, 300);
  return back(reqUrl, isLoggedIn ? loggedInReturn : '/sign-in', params);
}

/** Auth.js v5 default cookie names: secure prefix in HTTPS. */
function sessionCookieName(): string {
  const secure = (process.env.NEXTAUTH_URL ?? '').startsWith('https://');
  return secure ? '__Secure-authjs.session-token' : 'authjs.session-token';
}

async function signInAs(userId: string, tenantId: string, locale = 'uz', role = 'owner') {
  const cookieName = sessionCookieName();
  const secret = process.env.AUTH_SECRET;
  if (!secret) throw new Error('AUTH_SECRET not configured');

  const maxAgeSec = 30 * 24 * 60 * 60; // 30 days, matches Auth.js default
  const token = await encode({
    token: {
      sub: userId,
      tenantId,
      locale,
      role,
    },
    secret,
    salt: cookieName,
    maxAge: maxAgeSec,
  });

  const jar = await cookies();
  jar.set(cookieName, token, {
    httpOnly: true,
    secure: cookieName.startsWith('__Secure-'),
    sameSite: 'lax',
    path: '/',
    maxAge: maxAgeSec,
  });
}

export async function GET(req: Request) {
  const session = await auth();
  const isLoggedIn = Boolean(session?.user?.id && session.user.tenantId);
  const reqUrl = new URL(req.url);

  const error = reqUrl.searchParams.get('error');
  const errorReason = reqUrl.searchParams.get('error_reason');
  if (error) {
    return errorBack(reqUrl, isLoggedIn, errorReason ?? error);
  }

  const code = reqUrl.searchParams.get('code');
  const state = reqUrl.searchParams.get('state');
  if (!code || !state) {
    return errorBack(reqUrl, isLoggedIn, 'invalid_callback');
  }

  const jar = await cookies();
  const savedState = jar.get('ig_oauth_state')?.value;
  const ret = jar.get('ig_oauth_return')?.value ?? '/dashboard';
  const mode = (jar.get('ig_oauth_mode')?.value as 'connect' | 'signin') ?? 'connect';
  jar.delete('ig_oauth_state');
  jar.delete('ig_oauth_return');
  jar.delete('ig_oauth_mode');

  if (!savedState || state !== savedState) {
    return errorBack(reqUrl, isLoggedIn, 'state_mismatch');
  }

  try {
    // 1. Code → short-lived → long-lived (60d).
    const shortLived = await exchangeCode(code);
    const longLived = await exchangeLongLived(shortLived.access_token);
    const profile = await fetchProfile(longLived.access_token);

    // 2. Resolve which (User, Tenant) this IG account belongs to.
    let userId: string;
    let tenantId: string;
    let isNewSignup = false;

    // A 30-day JWT can outlive its DB row: orphan_cleanup may delete a half-
    // onboarded tenant, leaving a "ghost session" whose tenantId no longer
    // exists. Creating an InstagramAccount against it throws a FK violation
    // (instagram_accounts_tenantId_fkey). Verify the session row still exists;
    // if it's gone, fall through to find-or-create and re-mint the session.
    let sessionValid = false;
    if (mode === 'connect' && session?.user?.id && session.user.tenantId) {
      sessionValid = Boolean(
        await prisma.user.findFirst({
          where: { id: session.user.id, tenantId: session.user.tenantId },
          select: { id: true },
        }),
      );
    }

    if (sessionValid && session?.user?.id && session.user.tenantId) {
      userId = session.user.id;
      tenantId = session.user.tenantId;
    } else {
      // Real signin OR a stale 'connect' whose user/tenant was orphan-cleaned:
      // look up by IG user-id, else create fresh.
      const existing = await prisma.instagramAccount.findUnique({
        where: { instagramUserId: profile.id },
        select: { userId: true, tenantId: true },
      });
      if (existing) {
        userId = existing.userId;
        tenantId = existing.tenantId;
      } else {
        // Create a fresh tenant + user. Email placeholder uses IG handle
        // so the unique constraint passes; the user can rename later.
        const igUsername = profile.username || `ig-${profile.id}`;
        const placeholderEmail = `${igUsername}@instagram.local`;
        const dupe = await prisma.user.findUnique({ where: { email: placeholderEmail } });
        if (dupe) {
          // Username collision (very rare). Salt with timestamp.
          const salted = `${igUsername}-${Date.now()}@instagram.local`;
          const tenant = await prisma.tenant.create({
            data: { name: igUsername, type: 'personal' },
          });
          const user = await prisma.user.create({
            data: {
              tenantId: tenant.id,
              email: salted,
              name: profile.name ?? igUsername,
              role: 'owner',
            },
          });
          userId = user.id;
          tenantId = tenant.id;
        } else {
          const tenant = await prisma.tenant.create({
            data: { name: igUsername, type: 'personal' },
          });
          const user = await prisma.user.create({
            data: {
              tenantId: tenant.id,
              email: placeholderEmail,
              name: profile.name ?? igUsername,
              role: 'owner',
            },
          });
          userId = user.id;
          tenantId = tenant.id;
        }
        isNewSignup = true;
        // New IG-first tenant → seed a free subscription (idempotent, non-fatal).
        await ensureFreeSubscription(tenantId).catch(() => {});
      }
    }

    const db = prismaForTenant(tenantId);
    const expiresAt = new Date(Date.now() + longLived.expires_in * 1000);
    const rawAccountType = (profile.account_type ?? '').toLowerCase();
    // Personal IG accounts don't support Graph API insights/comments and our
    // pipeline can't work with them. Refuse the connection up front with a
    // clear, step-by-step recovery message rather than letting the user
    // discover broken features later.
    if (rawAccountType === 'personal') {
      void notifyTelegram(
        `📷 IG OAuth rad etildi · personal_account · @${profile.username} · tenant=${tenantId}`,
      );
      // Signup-wizard users (ret != /dashboard, e.g. /sign-up) must go BACK to
      // the wizard, where the ig_error branch resumes the chat with a manual-
      // handle fallback. Hard-redirecting them to /onboarding/profile-review
      // abandoned the wizard mid-flow — and personal accounts are the common
      // default in UZ, so this silently dead-ended most fresh signups.
      const personalLanding =
        ret && ret !== '/dashboard' ? ret : '/onboarding/profile-review';
      // AUTH-1: the /onboarding/profile-review recovery page is in the (onboarding) group, whose
      // layout redirects to /sign-in when there's no session. This early return skips the session
      // mint at step 6, so an anonymous /sign-in with a personal account landed there with NO session
      // → bounced to /sign-in (banner never rendered) and a fresh orphan tenant created on every
      // retry. Mint the session now (mirroring step 6) so the user reaches the recovery page
      // authenticated and a retry re-uses the same tenant. The signup-wizard path stays anonymous.
      if (personalLanding === '/onboarding/profile-review' && (mode === 'signin' || !sessionValid)) {
        await signInAs(userId, tenantId);
      }
      return back(reqUrl, personalLanding, { ig_error: 'personal_account' });
    }
    const accountType = rawAccountType === 'creator' ? 'creator' : 'business';

    // 3. Mirror the profile picture so its URL survives the IG CDN's token expiry.
    const mirroredAvatar = profile.profile_picture_url
      ? await mirrorInstagramAsset(profile.profile_picture_url, tenantId, 'avatar')
      : null;

    // The InstagramAccount table has TWO unique constraints:
    //   (1) (tenantId, handle) — for tenant-scoped manual handle lookups
    //   (2) instagramUserId    — globally unique because IG accounts can
    //                            only be linked to one tenant at a time
    //
    // The old code did `upsert(where: tenantId_handle)` which only matches
    // constraint #1, so a row with the SAME instagramUserId but a DIFFERENT
    // handle (or in a different tenant from a previous test) would trigger
    // a constraint #2 violation: "Unique constraint failed on instagramUserId".
    //
    // New flow: look up by instagramUserId globally FIRST.
    //   - found in CURRENT tenant → update in place
    //   - found in DIFFERENT tenant → refuse with a clear error (the IG
    //                                  account is already linked elsewhere)
    //   - not found → create fresh
    const existingByIgUserId = await prisma.instagramAccount.findUnique({
      where: { instagramUserId: profile.id },
      select: { id: true, tenantId: true, handle: true },
    });

    // Also reconcile constraint #1. A manual-handle onboarding row (the common
    // UZ fallback when the anonymous probe is datacenter-IP-blocked) is created
    // with instagramUserId = NULL, so the lookup above MISSES it. Without this,
    // the create branch below would hit @@unique([tenantId, handle]) → P2002 →
    // exchange_failed, permanently dead-ending OAuth for anyone who onboarded
    // via the manual handle. Scoped to THIS tenant, so it can't adopt a foreign
    // row (the cross-tenant theft guard below still keys off instagramUserId).
    const existing =
      existingByIgUserId ??
      (await prisma.instagramAccount.findUnique({
        where: { tenantId_handle: { tenantId, handle: profile.username } },
        select: { id: true, tenantId: true, handle: true },
      }));

    if (existingByIgUserId && existingByIgUserId.tenantId !== tenantId) {
      // The IG account is already linked to a different SMM Coach user.
      // Don't silently steal it — that's a data-integrity hazard.
      console.warn(
        '[instagram-oauth] account already linked to another tenant',
        {
          ig_user_id: profile.id,
          attempting_tenant: tenantId,
          existing_tenant: existingByIgUserId.tenantId,
        },
      );
      void notifyTelegram(
        `📷 IG OAuth rad etildi · already_linked · @${existingByIgUserId.handle} · ` +
          `attempting=${tenantId} · existing=${existingByIgUserId.tenantId}`,
      );
      return errorBack(
        reqUrl,
        isLoggedIn,
        'already_linked',
        `Bu Instagram akkaunt (@${existingByIgUserId.handle}) boshqa SMM Coach foydalanuvchisiga bog'langan.`,
      );
    }

    // Update by primary key if found (by instagramUserId OR same-tenant handle),
    // otherwise create. This sidesteps the upsert's where-clause limitations AND
    // adopts a pre-existing manual-handle row instead of colliding with it.
    const ig = existing
      ? await db.instagramAccount.update({
          where: { id: existing.id },
          data: {
            instagramUserId: profile.id,
            userId,  // re-bind to current user (e.g. if they re-OAuth'd)
            handle: profile.username,  // user might have renamed their IG handle
            accountType,
            verified: true,
            verificationMethod: 'oauth',
            oauthAccessTokenEnc: encryptToken(longLived.access_token),
            oauthExpiresAt: expiresAt,
            oauthScopes: [...REQUIRED_SCOPES],
            bio: profile.biography ?? null,
            avatarUrl: mirroredAvatar ?? profile.profile_picture_url ?? null,
            followerCount: profile.followers_count ?? 0,
            followingCount: profile.follows_count ?? 0,
            postsCount: profile.media_count ?? 0,
            lastSyncedAt: new Date(),
          },
        })
      : await db.instagramAccount.create({
          data: {
            tenantId,
            userId,
            handle: profile.username,
            instagramUserId: profile.id,
            accountType,
            verified: true,
            verificationMethod: 'oauth',
            oauthAccessTokenEnc: encryptToken(longLived.access_token),
            oauthExpiresAt: expiresAt,
            oauthScopes: [...REQUIRED_SCOPES],
            bio: profile.biography ?? null,
            avatarUrl: mirroredAvatar ?? profile.profile_picture_url ?? null,
            followerCount: profile.followers_count ?? 0,
            followingCount: profile.follows_count ?? 0,
            postsCount: profile.media_count ?? 0,
            lastSyncedAt: new Date(),
          },
        });

    // (the previous db.instagramAccount.upsert was replaced by the
    //  find-by-instagramUserId + update-or-create flow above)

    // 4. Full account sync (ALL posts + insights + mirrored thumbnails/videos +
    //    comment text + audience demographics) → our own store. Runs
    //    FIRE-AND-FORGET so OAuth returns instantly; the onboarding loading
    //    screen polls `instagram_accounts.syncProgress`. The previous inline
    //    50-post seed silently dropped the back-catalogue and never pulled
    //    comments — the sync orchestrator handles pagination + comments + video.
    void syncInstagramAccount({
      tenantId,
      igAccountId: ig.id,
      igUserId: profile.id,
      accessToken: longLived.access_token,
      userId,
    });

    // 5. Kick off the profile audit (agents service, profile_auditor node) so
    //    /onboarding/profile-review has a ready checklist. Fire-and-forget —
    //    never block OAuth on the LLM; the page polls for the result.
    try {
      const onboarding = await prisma.onboardingProfile.findFirst({
        where: { tenantId },
        select: { niche: true, currentFollowers: true, targetFollowers: true, deadline: true },
      });
      const monthsToGoal = onboarding?.deadline
        ? Math.max(
            1,
            Math.round((onboarding.deadline.getTime() - Date.now()) / (1000 * 60 * 60 * 24 * 30)),
          )
        : 6;
      await dispatchProfileAudit({
        tenantId,
        userId,
        igAccountId: ig.id,
        profile,
        niche: onboarding?.niche ?? null,
        goal: onboarding
          ? {
              current: onboarding.currentFollowers,
              target: onboarding.targetFollowers,
              months: monthsToGoal,
            }
          : null,
        wait: false,
      });
    } catch (err) {
      console.warn('[instagram-oauth] profile audit skipped:', (err as Error).message);
    }

    // 6. Forge an Auth.js JWT cookie for a real signin flow, OR when we just
    //    recovered a stale 'connect' (its old JWT points at a deleted
    //    user/tenant) — re-mint so the rest of the app stops using the ghost
    //    tenantId. A valid connect already has a good session.
    if (mode === 'signin' || !sessionValid) {
      await signInAs(userId, tenantId);
    }

    // 7. Pick the post-success landing.
    //
    // The (dashboard) layout has a guard that redirects users with
    // onboardingDone=true + roadmapReady=false straight to /onboarding/loading.
    // If we redirect those users to /dashboard or /onboarding/profile-review
    // they get bounced anyway — and the bounce loses the `?ig=connected`
    // toast trigger. Cut the middle-man: detect that state and send them
    // DIRECTLY to /onboarding/loading with the same flag.
    const roadmapActive = await prisma.roadmap.findFirst({
      where: { tenantId, status: 'active' },
      select: { id: true },
    });
    const onboardingDone = await prisma.onboardingProfile.count({
      where: { tenantId },
      take: 1,
    });

    let target: string;
    if ((mode === 'signin' || !sessionValid) && isNewSignup) {
      // Brand-new account (real signin or recovered ghost-connect) — send to
      // the onboarding wizard.
      target = '/onboarding';
    } else if (onboardingDone > 0 && !roadmapActive) {
      // Roadmap is mid-generation — keep the user where they can watch it.
      target = '/onboarding/loading';
    } else if (ret === '/dashboard') {
      // A mid-signup user (no OnboardingProfile yet) who reconnects via a
      // default-return link must resume the wizard, not divert to the
      // dashboard-oriented profile-review page (which discards in-progress
      // answers). Real dashboard reconnects still get profile-review.
      target = onboardingDone === 0 ? '/sign-up' : '/onboarding/profile-review';
    } else {
      target = ret;
    }
    const returnUrl = new URL(target.startsWith('/') ? target : '/dashboard', publicBase(reqUrl));
    returnUrl.searchParams.set('ig', 'connected');
    // Tell the landing page EXACTLY what happened so it can show an
    // unambiguous banner. The "Instagram bilan kirish" button silently does
    // one of three things and the user couldn't tell which: linked IG to the
    // account they were already in (connect), signed into a pre-existing
    // account matched by IG user-id (existing), or created a brand-new
    // account+tenant (new). Surface it.
    returnUrl.searchParams.set(
      'ig_account',
      mode === 'connect' ? 'linked' : isNewSignup ? 'new' : 'existing',
    );
    void notifyTelegram(
      `📷 Instagram ulandi · @${profile.username} · tenant=${tenantId} · ` +
        `type=${accountType} · followers=${profile.followers_count ?? 0} · posts=${profile.media_count ?? 0} · ` +
        `mode=${mode}` +
        (isNewSignup ? ' · NEW_USER' : ''),
    );
    return NextResponse.redirect(returnUrl);
  } catch (err) {
    console.error('[instagram-oauth] callback failed:', err);
    // Extract Meta's actual error text so the user sees WHY it failed.
    // Common Meta messages: "Invalid redirect_uri", "Application is not
    // approved for this scope", "Invalid platform app", "Invalid client_id".
    const msg = err instanceof Error ? err.message : 'exchange_failed';
    const lower = msg.toLowerCase();
    const code = lower.includes('redirect_uri') || lower.includes('redirect uri')
      ? 'invalid_redirect_uri'
      : lower.includes('scope')
      ? 'scope_not_approved'
      : lower.includes('client_id') || lower.includes('platform app')
      ? 'invalid_app_id'
      : 'exchange_failed';
    // Pass Meta's raw message into the banner so the user sees the literal
    // reason, not just a code. Strip noisy prefixes.
    const detail = msg.replace(/^Instagram .+? failed: \d+\s*/, '').trim();
    void notifyTelegram(
      `❌ IG OAuth xato · ${code} · mode=${mode} · "${detail.slice(0, 120)}"`,
    );
    // Return to wherever the flow started (e.g. /sign-up for the onboarding
    // connect step) so the chat can resume + show the error inline, instead of
    // dumping the user on /dashboard mid-onboarding.
    return errorBack(reqUrl, isLoggedIn, code, detail, ret);
  }
}
