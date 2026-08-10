/**
 * POST /api/settings/voice — save the tenant's global voice-over persona
 * (Settings → Ovoz). Body: { voiceName, style, speed }. The saved voice is used
 * by BOTH the reel voice-over (media pipeline) and the agents voice coach.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';
import { saveTenantVoiceSettings } from '@/lib/voice/voice-prefs';
import type { VoiceSettings } from '@/lib/voice/uzbek-voice-options';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }
  const body = (await req.json().catch(() => ({}))) as Partial<VoiceSettings>;
  try {
    const settings = await saveTenantVoiceSettings(session.user.tenantId, body);
    return NextResponse.json({ ok: true, settings });
  } catch (err) {
    return NextResponse.json(
      { message: (err as Error).message || 'Saqlanmadi' },
      { status: 500 },
    );
  }
}
