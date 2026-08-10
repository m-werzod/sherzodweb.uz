/**
 * POST /api/tasks/[id]/comments/draft — classify one comment and draft a reply
 * in the user's voice. Body: { text, commentId?, username? }. Returns
 * { kind, reply }. The user reviews + edits before sending (the reply route is
 * the action). Mirrors the voice coach's web-side OpenAI usage. NEVER auto-sends.
 *
 * Stage 12: when the comment is classified as an actionable lead (sales intent)
 * or a question, we persist it to `leads` so it shows up in the leads inbox even
 * if the user never sends the reply. This is the manual mirror of the autonomous
 * `comment_sentinel` lead pass.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const BodySchema = z.object({
  text: z.string().trim().min(1).max(1000),
  commentId: z.string().trim().max(200).optional(),
  username: z.string().trim().max(200).optional(),
});

const KINDS = ['question', 'lead', 'praise', 'criticism', 'spam'] as const;
// Kinds that belong in the sales funnel and get a `leads` row.
const ACTIONABLE = new Set(['lead', 'question']);

export async function POST(req: Request, ctx: { params: Promise<{ id: string }> }) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const { id: taskId } = await ctx.params;
  const key = process.env.OPENAI_API_KEY;
  if (!key) {
    return NextResponse.json({ error: 'not_configured', message: 'AI sozlanmagan' }, { status: 503 });
  }
  const parsed = BodySchema.safeParse(await req.json().catch(() => ({})));
  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid' }, { status: 400 });
  }

  // Light brand context so the reply sounds like the user.
  const db = prismaForTenant(session.user.tenantId);
  const ob = await db.onboardingProfile
    .findFirst({ select: { nicheDetail: true, brandVoice: true } })
    .catch(() => null);

  const system =
    'Sen Instagram blogerining ChatPlace yordamchisisan. Senga BITTA izoh beriladi. ' +
    '(1) Uni tasniflab ber: question (savol), lead (mijoz/sotuv qiziqishi — narx, sotib olish, hamkorlik), ' +
    'praise (maqtov), criticism (tanqid/shikoyat), spam. ' +
    '(2) Blogger nomidan QISQA, samimiy, o\'zbekcha javob yoz (1-2 jumla, emoji o\'rinli bo\'lsa mayli). ' +
    'Lead bo\'lsa — muloyim qiziqtirib, DM/keyingi qadamga yo\'naltir. Spam bo\'lsa — reply bo\'sh qoldir. ' +
    (ob?.nicheDetail ? `Soha: ${String(ob.nicheDetail).slice(0, 200)}. ` : '') +
    (ob?.brandVoice ? `Ohang: ${String(ob.brandVoice).slice(0, 200)}. ` : '') +
    'JSON qaytar: {"kind":"...","reply":"..."}. Faqat JSON.';

  try {
    const res = await fetch('https://api.openai.com/v1/chat/completions', {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'content-type': 'application/json' },
      body: JSON.stringify({
        model: 'gpt-4o-mini',
        max_tokens: 300,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: system },
          { role: 'user', content: parsed.data.text },
        ],
      }),
      signal: AbortSignal.timeout(20_000),
    });
    if (!res.ok) {
      return NextResponse.json({ error: 'llm_failed', message: `AI ${res.status}` }, { status: 502 });
    }
    const j = (await res.json()) as { choices?: Array<{ message?: { content?: string } }> };
    const raw = j.choices?.[0]?.message?.content ?? '{}';
    const parsedOut = JSON.parse(raw) as { kind?: string; reply?: string };
    const kind = (KINDS as readonly string[]).includes(parsedOut.kind ?? '') ? parsedOut.kind : 'question';
    const reply = (parsedOut.reply ?? '').trim();

    // Persist actionable leads (sales intent / question). Best-effort — a DB
    // hiccup must not break the draft response the user is waiting on. Dedupe on
    // (tenantId, commentId) so re-drafting the same comment updates, not dupes.
    if (kind && ACTIONABLE.has(kind) && parsed.data.commentId) {
      try {
        const post = await db.contentTask
          .findUnique({ where: { id: taskId }, select: { instagramPostId: true } })
          .catch(() => null);
        await db.lead.upsert({
          where: {
            tenantId_commentId: { tenantId: session.user.tenantId, commentId: parsed.data.commentId },
          },
          create: {
            tenantId: session.user.tenantId,
            commentId: parsed.data.commentId,
            commentText: parsed.data.text,
            igUsername: parsed.data.username ?? null,
            intent: kind,
            taskId,
            postId: post?.instagramPostId ?? null,
            draftReply: reply || null,
          },
          update: { intent: kind, draftReply: reply || null },
        });
      } catch {
        /* best-effort: lead capture never blocks the draft */
      }
    }

    return NextResponse.json({ ok: true, kind, reply });
  } catch (e) {
    return NextResponse.json({ error: 'llm_failed', message: (e as Error).message.slice(0, 140) }, { status: 502 });
  }
}
