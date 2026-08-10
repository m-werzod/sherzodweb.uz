import { VoiceCoach } from '@/components/traj/voice-coach';

export default function VoicePage() {
  return (
    <div style={{ maxWidth: 640, margin: '0 auto', paddingTop: 8 }}>
      <div className="eyebrow" style={{ fontSize: 9, color: 'var(--accent)' }}>
        PROTOTIP
      </div>
      <h1 className="serif" style={{ fontSize: 30, margin: '6px 0 6px' }}>
        Ovozli murabbiy
      </h1>
      <p className="muted" style={{ fontSize: 14, lineHeight: 1.6, marginBottom: 20 }}>
        Real-time ovozli AI murabbiy — o&apos;zbekcha gaplashing, javobni eshiting.
        Whisper (nutq→matn) → Claude (murabbiy) → ElevenLabs (matn→nutq) zanjiri.
      </p>
      <VoiceCoach />
    </div>
  );
}
