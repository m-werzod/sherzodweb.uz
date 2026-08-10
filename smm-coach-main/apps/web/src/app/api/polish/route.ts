/**
 * POST /api/polish — clean a piece of (usually dictated) text with a cheap LLM.
 *
 * Body: { text, hint? }. Returns { text }. Powers the "✨ AI tozalash" button:
 * the user dictates raw, then taps to fix mis-hears/filler and tidy it into
 * clean written Uzbek (meaning preserved, no new facts). ~$0.0005 per call.
 *
 * NOT session-gated (matches /api/transcribe — used during anonymous signup).
 * Degrades to the input text unchanged on any failure.
 */
import { NextResponse } from 'next/server';
import { polishTranscript } from '@/lib/transcribe/polish';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const text = typeof body?.text === 'string' ? body.text : '';
  const hint = typeof body?.hint === 'string' ? body.hint : null;
  if (!text.trim()) {
    return NextResponse.json({ error: 'no_text' }, { status: 400 });
  }
  // polishTranscript returns the input unchanged when GROQ_API_KEY is absent or
  // the call fails, so this always yields usable text.
  const cleaned = await polishTranscript(text.slice(0, 4000), hint);
  return NextResponse.json({ text: cleaned });
}
