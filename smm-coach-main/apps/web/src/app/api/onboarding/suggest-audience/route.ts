/**
 * POST /api/onboarding/suggest-audience — infer a target audience from the
 * user's niche so the conversational onboarding can PROPOSE it (the user only
 * confirms/edits) instead of asking them to type it from scratch.
 *
 * Body: { niche: string, nicheDetail?: string }
 * Returns: { audience: string }  — 1-2 Uzbek sentences. Always 200; on any LLM
 * failure it returns a sensible niche-derived fallback so the UI never blocks.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const ANTHROPIC_API = 'https://api.anthropic.com/v1/messages';
// Haiku — cheap + fast; this is a one-line inference, not deep reasoning.
const MODEL = 'claude-haiku-4-5';

function fallback(niche: string): string {
  return `${niche} sohasiga qiziquvchi O'zbekistondagi 18-35 yoshli auditoriya. (AI keyingi tahlilda aniqlashtiradi.)`;
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const body = (await req.json().catch(() => null)) as
    | { niche?: string; nicheDetail?: string }
    | null;
  const niche = (body?.niche || '').trim().slice(0, 120);
  if (!niche) return NextResponse.json({ audience: '' });

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) return NextResponse.json({ audience: fallback(niche) });

  const detail = (body?.nicheDetail || '').trim().slice(0, 600);
  const prompt =
    `Soha: ${niche}\n` +
    (detail ? `Tafsilot: ${detail}\n` : '') +
    `\nShu O'zbekistondagi Instagram blogeri uchun ASOSIY maqsadli auditoriyani 1-2 ` +
    `qisqa o'zbekcha jumlada tasvirla (yosh, jins, joylashuv, qiziqish/ehtiyoj). ` +
    `Faqat tavsifning O'ZINI qaytar — sarlavha, izoh yoki qo'shtirnoqsiz.`;

  try {
    const res = await fetch(ANTHROPIC_API, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': apiKey,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({
        model: MODEL,
        max_tokens: 220,
        messages: [{ role: 'user', content: prompt }],
      }),
      signal: AbortSignal.timeout(12_000),
    });
    if (!res.ok) return NextResponse.json({ audience: fallback(niche) });
    const json = (await res.json()) as { content?: Array<{ type: string; text?: string }> };
    const text = (json.content?.find((c) => c.type === 'text')?.text ?? '').trim();
    return NextResponse.json({ audience: text.slice(0, 600) || fallback(niche) });
  } catch {
    return NextResponse.json({ audience: fallback(niche) });
  }
}
