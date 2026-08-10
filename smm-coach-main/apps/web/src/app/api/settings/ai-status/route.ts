/**
 * GET /api/settings/ai-status
 *
 * Returns which AI providers are wired (env key present) and which
 * features they unlock. Used by the Settings page to render the
 * "AI providers" section with green/grey dots so the user can see at
 * a glance what's live and what's still missing a key.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

type Provider = {
  id: string;
  name: string;
  description: string;
  configured: boolean;
  /** Where to get a key. */
  signupUrl: string;
  /** Features the provider unlocks when configured. */
  features: string[];
  /** Tier: 'core' (required for basic flow) | 'premium' (faza 2 / paid). */
  tier: 'core' | 'premium' | 'faza2';
};

export async function GET() {
  const session = await auth();
  if (!session?.user) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const providers: Provider[] = [
    {
      id: 'anthropic',
      name: 'Anthropic Claude',
      description: 'Scriptwriter (Opus 4), critique (Sonnet 4.6), validators (Haiku 4.5)',
      configured: !!process.env.ANTHROPIC_API_KEY,
      signupUrl: 'https://console.anthropic.com/settings/billing',
      features: ['Script generation', 'Brand voice', 'Drift detection', 'Output validation'],
      tier: 'core',
    },
    {
      id: 'gemini',
      name: 'Google Gemini',
      description: '2.5 Pro/Flash + embeddings + Imagen 3 thumbnails',
      configured: !!process.env.GEMINI_API_KEY,
      signupUrl: 'https://aistudio.google.com/apikey',
      features: ['Market analyst', 'Vision (IG photos)', 'Embeddings (free)', 'Imagen 3'],
      tier: 'core',
    },
    {
      id: 'groq',
      name: 'Groq (Llama 3.3)',
      description: '700 tok/sec — Account Tracker classification at scale',
      configured: !!process.env.GROQ_API_KEY,
      signupUrl: 'https://console.groq.com/keys',
      features: ['Fast classifier', 'Whisper Large v3'],
      tier: 'core',
    },
    {
      id: 'elevenlabs',
      name: 'ElevenLabs',
      description: 'TTS voiceover, voice cloning',
      configured: !!process.env.ELEVENLABS_API_KEY,
      signupUrl: 'https://elevenlabs.io/app/subscription',
      features: ['Voiceover audio', 'Voice cloning'],
      tier: 'core',
    },
    {
      id: 'openai',
      name: 'OpenAI',
      description: 'Whisper transcription, DALL-E fallback, GPT-4o emergency fallback',
      configured: !!process.env.OPENAI_API_KEY,
      signupUrl: 'https://platform.openai.com/api-keys',
      features: ['Video → text', 'DALL-E thumbnails', 'GPT-4o fallback'],
      tier: 'premium',
    },
    {
      id: 'heygen',
      name: 'HeyGen Avatar IV',
      description: 'Talking-head video with lipsync — Premium tier feature',
      configured: !!process.env.HEYGEN_API_KEY,
      signupUrl: 'https://app.heygen.com/settings/api',
      features: ['Avatar video', 'Lipsync'],
      tier: 'premium',
    },
    {
      id: 'runway',
      name: 'Runway Gen-3',
      description: 'AI video generation (B-roll, video-to-video)',
      configured: !!process.env.RUNWAY_API_KEY,
      signupUrl: 'https://runwayml.com/pricing',
      features: ['B-roll clips', 'Video-to-video'],
      tier: 'faza2',
    },
  ];

  const summary = {
    core: providers.filter((p) => p.tier === 'core'),
    premium: providers.filter((p) => p.tier === 'premium'),
    faza2: providers.filter((p) => p.tier === 'faza2'),
    coreReady: providers.filter((p) => p.tier === 'core').every((p) => p.configured),
    premiumReady: providers.filter((p) => p.tier === 'premium').every((p) => p.configured),
  };

  return NextResponse.json({ providers, summary });
}
