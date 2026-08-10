/**
 * POST /api/admin/wipe?confirm=YES_WIPE_EVERYTHING
 *
 * Nukes ALL tenant data — users, tenants, roadmaps, tasks, IG accounts,
 * onboarding profiles, agent runs, LLM call logs, everything. Designed
 * for a fresh-start scenario where you want to throw away test data and
 * begin from scratch.
 *
 * Safety:
 *   - Requires a PLATFORM ADMIN session (ADMIN_EMAILS allowlist) — not just
 *     any authenticated user.
 *   - Requires the literal `?confirm=YES_WIPE_EVERYTHING` query param
 *     so a stray click can't fire it.
 *   - Cross-tenant SharedKnowledge cache is PRESERVED — it's slow to
 *     rebuild (4-6h seeder cycle) and contains no PII.
 *   - Returns a per-table delete count receipt so you can audit what
 *     went away.
 *
 * After running: rotate AUTH_SECRET to invalidate any in-flight session
 * cookies (your own session will be killed by the User table truncate
 * anyway, but it's still good hygiene).
 *
 * Delete this endpoint file after use — it's a footgun.
 */
import { NextResponse } from 'next/server';
import { getAdminSession } from '@/lib/auth/admin';
import { prisma } from '@smm/db';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const CONFIRM_TOKEN = 'YES_WIPE_EVERYTHING';

export async function POST(req: Request) {
  const session = await getAdminSession();
  if (!session) {
    return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  }
  const url = new URL(req.url);
  if (url.searchParams.get('confirm') !== CONFIRM_TOKEN) {
    return NextResponse.json(
      {
        error: 'missing_confirmation',
        hint: `Add ?confirm=${CONFIRM_TOKEN} to actually run the wipe.`,
      },
      { status: 400 },
    );
  }

  // Order matters: child rows first so FK cascades don't deadlock.
  // Most of these FK with onDelete: Cascade, so deleting the parent
  // (Tenant) would suffice, but explicit per-table deletes give us a
  // clean count receipt.
  const receipt: Record<string, number> = {};

  // Per-task ancillaries
  receipt.taskChecklistItems = (await prisma.taskChecklistItem.deleteMany({})).count;
  receipt.taskAgentInsights = (await prisma.taskAgentInsight.deleteMany({})).count;
  receipt.taskAttachments = (await prisma.taskAttachment.deleteMany({})).count;
  receipt.taskMedia = (await prisma.taskMedia.deleteMany({})).count;
  receipt.scriptHistory = (await prisma.scriptHistory.deleteMany({})).count;

  // Roadmap content
  receipt.contentTasks = (await prisma.contentTask.deleteMany({})).count;
  receipt.contentPillars = (await prisma.contentPillar.deleteMany({})).count;
  receipt.roadmaps = (await prisma.roadmap.deleteMany({})).count;

  // Trajectory tables
  receipt.followerSnapshots = (await prisma.followerSnapshot.deleteMany({})).count;
  receipt.dailyActivity = (await prisma.dailyActivity.deleteMany({})).count;
  receipt.audienceSnapshots = (await prisma.audienceSnapshot.deleteMany({})).count;
  receipt.competitorTracks = (await prisma.competitorTrack.deleteMany({})).count;
  receipt.forecasts = (await prisma.forecast.deleteMany({})).count;
  receipt.predictionAudits = (await prisma.predictionAudit.deleteMany({})).count;
  receipt.agentMessages = (await prisma.agentMessage.deleteMany({})).count;

  // Instagram + onboarding
  receipt.instagramPosts = (await prisma.instagramPost.deleteMany({})).count;
  receipt.onboardingProfiles = (await prisma.onboardingProfile.deleteMany({})).count;
  receipt.instagramAccounts = (await prisma.instagramAccount.deleteMany({})).count;

  // Agent + observability
  receipt.tokenUsages = (await prisma.tokenUsage.deleteMany({})).count;
  receipt.llmCalls = (await prisma.lLMCall.deleteMany({})).count;
  receipt.agentMemories = (await prisma.agentMemory.deleteMany({})).count;
  receipt.agentRuns = (await prisma.agentRun.deleteMany({})).count;

  // Payments + subscriptions
  receipt.paymentEvents = (await prisma.paymentEvent.deleteMany({})).count;
  receipt.subscriptions = (await prisma.subscription.deleteMany({})).count;

  // Webhook dedupe log (cross-tenant, but tied to past activity)
  receipt.webhookEvents = (await prisma.webhookEvent.deleteMany({})).count;

  // Auth.js tables — these hold the OAuth links + sessions + verification
  // tokens. Wipe so previous Google/IG OAuth bindings don't auto-restore
  // a half-deleted user on next login.
  receipt.sessions = (await prisma.session.deleteMany({})).count;
  receipt.accounts = (await prisma.account.deleteMany({})).count;
  receipt.verificationTokens = (await prisma.verificationToken.deleteMany({})).count;

  // Finally users + tenants. User has FK to Tenant; delete users first.
  receipt.users = (await prisma.user.deleteMany({})).count;
  receipt.tenants = (await prisma.tenant.deleteMany({})).count;

  const totalRowsDeleted = Object.values(receipt).reduce((a, b) => a + b, 0);

  return NextResponse.json({
    ok: true,
    totalRowsDeleted,
    deletedAt: new Date().toISOString(),
    receipt,
    note:
      'SharedKnowledge cache preserved (cross-tenant, slow to rebuild). ' +
      'Your session is now invalid because your User row was deleted — ' +
      'clear cookies and sign up again. Recommend rotating AUTH_SECRET ' +
      'in Coolify env after this op for hygiene.',
    nextSteps: [
      '1. Clear browser cookies for smm.brotech.uz',
      '2. Visit /sign-up to create a fresh account',
      '3. (Optional) Rotate AUTH_SECRET in Coolify env vars',
      '4. (Recommended) Delete this endpoint file from the repo and redeploy',
    ],
  });
}
