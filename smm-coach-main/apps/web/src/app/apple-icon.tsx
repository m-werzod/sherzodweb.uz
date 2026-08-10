import { ImageResponse } from 'next/og';

// Next.js's metadata "apple-icon" route ONLY accepts {ico,jpg,jpeg,png}.
// An apple-icon.svg sibling file is silently ignored — iOS Safari then
// falls back to a generic globe icon when the tab is added to the home
// screen or shown in the tab-overview thumbnail. So we render the brand
// mark via ImageResponse (Satori → resvg) which emits real PNG at build.

export const size = { width: 180, height: 180 };
export const contentType = 'image/png';

export default function AppleIcon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '100%',
          height: '100%',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          // Bottom-left -> top-right brand gradient (purple -> magenta).
          background: 'linear-gradient(45deg, #7C3AED 0%, #D946EF 100%)',
          borderRadius: 42,
        }}
      >
        <svg
          width="180"
          height="180"
          viewBox="0 0 120 120"
          xmlns="http://www.w3.org/2000/svg"
        >
          {/* Subtle trail behind the S */}
          <path
            d="M 22 92 Q 50 88, 60 60 T 92 28"
            stroke="#F9F8FB"
            strokeWidth="6"
            fill="none"
            strokeLinecap="round"
            opacity="0.22"
          />
          {/* The S monogram */}
          <path
            d="M 80 38 Q 56 38, 56 52 Q 56 60, 70 62 Q 86 64, 86 76 Q 86 90, 62 90"
            stroke="#F9F8FB"
            strokeWidth="9"
            fill="none"
            strokeLinecap="round"
          />
          {/* Spark at the end of the trail */}
          <circle cx="92" cy="28" r="7" fill="#F9F8FB" />
          <circle cx="92" cy="28" r="3.5" fill="#D946EF" />
        </svg>
      </div>
    ),
    { ...size },
  );
}
