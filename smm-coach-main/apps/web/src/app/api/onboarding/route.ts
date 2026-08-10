import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';
import { OnboardingPayloadSchema } from '@smm/shared-types';
import { invokeWorkflow, extractPsychProfile, type InterviewMsg } from '@/lib/agents/client';
import { ensurePostAnalysis } from '@/lib/instagram/run-analysis';
import { notifyTelegram } from '@/lib/telegram';

// Probe-harvested post timestamps — optional companion field that lives
// alongside the (locked) shared OnboardingPayloadSchema. Parsed separately
// so the agents service's payload contract stays unchanged.
const RecentPostsSchema = z
  .array(z.object({ shortcode: z.string().min(1).max(40), takenAt: z.number().int().positive() }))
  .max(50)
  .optional();

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const body = await req.json().catch(() => null);
  const parsed = OnboardingPayloadSchema.safeParse(body);
  if (!parsed.success) {
    // Log the exact rejected fields — a bare 400 here silently stalls the
    // whole onboarding (no profile, no roadmap dispatch) and used to be
    // invisible server-side.
    console.error(
      '[onboarding] payload rejected by OnboardingPayloadSchema:',
      JSON.stringify(parsed.error.issues),
    );
    return NextResponse.json({ error: 'invalid', issues: parsed.error.issues }, { status: 400 });
  }
  const recentPosts = RecentPostsSchema.safeParse(
    body && typeof body === 'object' && 'recentPosts' in body ? body.recentPosts : undefined,
  );

  // targetAudience is now optional (the conversational onboarding lets the AI
  // infer it). Fill a niche-derived default when absent so the required DB
  // column + agent prompts always have a value; the agent loop refines it.
  const targetAudience =
    parsed.data.targetAudience && parsed.data.targetAudience.trim().length > 0
      ? parsed.data.targetAudience
      : `Soha: ${parsed.data.niche}; UZ region; auditoriya AI tahlilida aniqlashtiriladi.`;

  const db = prismaForTenant(session.user.tenantId);
  const ig = await db.instagramAccount.upsert({
    where: {
      tenantId_handle: { tenantId: session.user.tenantId, handle: parsed.data.instagramHandle },
    },
    update: {},
    create: {
      tenantId: session.user.tenantId,
      userId: session.user.id,
      handle: parsed.data.instagramHandle,
      accountType: 'unknown',
    },
  });

  await db.onboardingProfile.upsert({
    where: { instagramAccountId: ig.id },
    update: {
      niche: parsed.data.niche,
      subNiche: parsed.data.subNiche,
      contentStyle: parsed.data.contentStyle,
      nicheDetail: parsed.data.nicheDetail,
      targetAudience,
      brandVoice: parsed.data.brandVoice,
      currentFollowers: parsed.data.currentFollowers,
      targetFollowers: parsed.data.targetFollowers,
      deadline: parsed.data.deadline ? new Date(parsed.data.deadline) : null,
      goalSummary: `${parsed.data.currentFollowers} → ${parsed.data.targetFollowers} in ${parsed.data.niche}`,
      primaryGoal: parsed.data.primaryGoal,
      secondaryGoal: parsed.data.secondaryGoal,
      goalWeight: parsed.data.goalWeight,
    },
    create: {
      tenantId: session.user.tenantId,
      instagramAccountId: ig.id,
      niche: parsed.data.niche,
      subNiche: parsed.data.subNiche,
      contentStyle: parsed.data.contentStyle,
      nicheDetail: parsed.data.nicheDetail,
      targetAudience,
      brandVoice: parsed.data.brandVoice,
      currentFollowers: parsed.data.currentFollowers,
      targetFollowers: parsed.data.targetFollowers,
      deadline: parsed.data.deadline ? new Date(parsed.data.deadline) : null,
      goalSummary: `${parsed.data.currentFollowers} → ${parsed.data.targetFollowers} in ${parsed.data.niche}`,
      primaryGoal: parsed.data.primaryGoal,
      secondaryGoal: parsed.data.secondaryGoal,
      goalWeight: parsed.data.goalWeight,
    },
  });

  // Copy the psychological profile captured DURING onboarding (stored on the
  // standalone PsychInterview before this profile row existed) onto the profile
  // so the agents read it via the knowledge vault + state persona. Best-effort:
  // the psych phase is optional and must never block the roadmap dispatch.
  try {
    const psych = await db.psychInterview.findFirst({ orderBy: { createdAt: 'desc' } });
    if (psych?.profile) {
      await db.onboardingProfile.update({
        where: { instagramAccountId: ig.id },
        data: { psychProfile: psych.profile, psychInterviewId: psych.id },
      });
    } else if (
      psych &&
      Array.isArray(psych.messages) &&
      (psych.messages as unknown[]).length > 0
    ) {
      // The transcript distillation is fired fire-and-forget at the end of the
      // psych phase; if it hasn't landed yet (slow Claude call vs a fast user),
      // extract it now so the copy is deterministic instead of racing.
      try {
        const out = await extractPsychProfile(
          session.user.tenantId,
          psych.messages as unknown as InterviewMsg[],
        );
        if (out.profile) {
          await db.psychInterview.update({
            where: { id: psych.id },
            data: { profile: out.profile, completedAt: new Date() },
          });
          await db.onboardingProfile.update({
            where: { instagramAccountId: ig.id },
            data: { psychProfile: out.profile, psychInterviewId: psych.id },
          });
        }
      } catch {
        /* best-effort — extraction is optional */
      }
    } else {
      // No psych interview at all (the email signup-chat funnel collects none). Derive a
      // BASELINE profile from the tone/brand/niche/goal answers we DID collect so
      // psychProfile is never null and the vault → scriptwriter chain still carries the
      // user's voice. Shallow but real; the extractor caps confidence + rejects hollow
      // shells, so a weak input yields null (= prior behaviour), never a fake profile.
      try {
        const a = parsed.data;
        const synth: InterviewMsg[] = [
          {
            role: 'assistant',
            content: 'Brendingiz ovozi qanday va nima haqida kontent qilasiz?',
          },
          {
            role: 'user',
            content: [
              a.brandVoice && `Brend ovozi: ${a.brandVoice}`,
              `Soha: ${a.niche}${a.subNiche ? ` / ${a.subNiche}` : ''}`,
              a.nicheDetail && `Tafsilot: ${a.nicheDetail}`,
              a.contentStyle && `Uslub: ${a.contentStyle}`,
              `Auditoriya: ${targetAudience}`,
            ]
              .filter(Boolean)
              .join('. '),
          },
          {
            role: 'assistant',
            content: 'Maqsadingiz nima va nega bu sohada ishlaysiz?',
          },
          {
            role: 'user',
            content: [
              `Asosiy maqsad: ${a.primaryGoal ?? 'belgilanmagan'}${a.secondaryGoal ? `, ikkilamchi: ${a.secondaryGoal}` : ''}`,
              `Obunachi: ${a.currentFollowers} dan ${a.targetFollowers} gacha`,
            ].join('. '),
          },
        ];
        const out = await extractPsychProfile(session.user.tenantId, synth);
        if (out.profile) {
          await db.onboardingProfile.update({
            where: { instagramAccountId: ig.id },
            data: { psychProfile: out.profile },
          });
        }
      } catch {
        /* best-effort — derived profile is optional */
      }
    }
  } catch {
    /* best-effort — psych profile is optional */
  }

  // Quantitative cadence → roadmap size: postsPerDay × days-to-deadline = N
  // topics. Written via raw SQL since the generated client may not type the
  // new columns until `prisma generate` runs at build.
  const postsPerDay = parsed.data.postsPerDay ?? null;
  if (postsPerDay) {
    const now = Date.now();
    const deadlineMs = parsed.data.deadline
      ? new Date(parsed.data.deadline).getTime()
      : now + 30 * 864e5;
    const days = Math.max(7, Math.round((deadlineMs - now) / 864e5));
    const roadmapSize = Math.min(400, Math.max(1, Math.round(postsPerDay * days)));
    await db.$executeRaw`
      UPDATE onboarding_profiles
      SET "postsPerDay" = ${postsPerDay}, "roadmapSize" = ${roadmapSize}
      WHERE "instagramAccountId" = ${ig.id}
    `;
  }

  // Seed real post dates into instagram_posts so the dashboard streak
  // heatmap shows actual activity immediately (instead of an empty 182-cell
  // grid until the Account Tracker workflow runs). Posts here are
  // metadata-only (shortcode + postedAt) — Account Tracker fills in
  // reach/likes/etc. on subsequent passes.
  if (recentPosts.success && recentPosts.data && recentPosts.data.length > 0) {
    // postId is a GLOBAL unique (not tenant/account scoped), so a bare upsert
    // keyed only on postId could touch a row owned by a *different* IG account
    // (e.g. another tenant tracking the same shortcode). Find-first, then only
    // write within this account's boundary — never overwrite a foreign row.
    await Promise.all(
      recentPosts.data.map(async (p) => {
        const postedAt = new Date(p.takenAt * 1000);
        const existing = await db.instagramPost.findUnique({
          where: { postId: p.shortcode },
          select: { instagramAccountId: true },
        });
        if (existing) {
          if (existing.instagramAccountId === ig.id) {
            await db.instagramPost.update({ where: { postId: p.shortcode }, data: { postedAt } });
          }
          return; // foreign account's post — leave it untouched
        }
        try {
          await db.instagramPost.create({
            data: {
              instagramAccountId: ig.id,
              postId: p.shortcode,
              shortcode: p.shortcode,
              postedAt,
              permalink: `https://instagram.com/p/${p.shortcode}/`,
            },
          });
        } catch (e) {
          // Concurrent create raced us to the same postId — benign, the row exists now.
          if (!(e instanceof Error && e.message.includes('P2002'))) throw e;
        }
      }),
    );
  }

  // Idempotency — if a roadmap_generation run for this tenant has been
  // dispatched in the last 10 minutes, return the same one instead of
  // kicking off a duplicate. Catches double-clicks, tab-duplicates, and
  // reload-while-submitting races; each would otherwise spawn its own
  // initial_analysis + roadmap_generator pair and double the bill.
  const recentRun = await db.agentRun.findFirst({
    where: {
      workflow: 'roadmap_generation',
      startedAt: { gte: new Date(Date.now() - 10 * 60 * 1000) },
      status: { in: ['queued', 'running', 'completed'] },
    },
    orderBy: { startedAt: 'desc' },
  });
  if (recentRun) {
    void notifyTelegram(
      `🔁 Onboarding reused · tenant=${session.user.tenantId} · runId=${recentRun.id} · status=${recentRun.status}`,
    );
    return NextResponse.json({
      ok: true,
      reused: true,
      run: { runId: recentRun.id, threadId: recentRun.threadId, status: recentRun.status },
    });
  }

  void notifyTelegram(
    `📝 Onboarding tugatildi · tenant=${session.user.tenantId} · ` +
      `niche=${parsed.data.niche} · ${parsed.data.currentFollowers}→${parsed.data.targetFollowers} followers · ` +
      `@${parsed.data.instagramHandle}`,
  );

  // Run the IG post analysis NOW (engagement health + topics) and store it on
  // the account, BEFORE the agent graph's initial_analysis reads it — this is
  // what seeds the vault + lets roadmap_generator skip already-covered topics.
  // Runs for BOTH onboarding paths (chat + conversational). Best-effort: a
  // failure must never block the roadmap dispatch.
  await ensurePostAnalysis(session.user.tenantId).catch(() => null);

  // Kick off the agent workflow that performs initial analysis + roadmap gen.
  // Pass an idempotency_key so the agents-side dispatcher also dedupes —
  // belt and braces against the brief window before the row above is written.
  const run = await invokeWorkflow({
    tenantId: session.user.tenantId,
    userId: session.user.id,
    workflow: 'roadmap_generation',
    input: { onboarding: parsed.data },
    idempotencyKey: `onboarding:${session.user.tenantId}:${Math.floor(Date.now() / (10 * 60 * 1000))}`,
  });

  void notifyTelegram(
    `🌳 Roadmap dispatch · roadmap_generation · tenant=${session.user.tenantId} · runId=${run.runId}`,
  );

  return NextResponse.json({ ok: true, run });
}
