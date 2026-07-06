import { splitHighlight } from '@/lib/i18n/getUI'

/** Renders text containing `**emphasized**` markers, styling the wrapped segments. */
export default function Highlight({ text, className = 'text-[#38bdf8] font-semibold' }: { text: string; className?: string }) {
  return (
    <>
      {splitHighlight(text).map((part, i) =>
        part.emphasis ? (
          <span key={i} className={className}>
            {part.text}
          </span>
        ) : (
          <span key={i}>{part.text}</span>
        )
      )}
    </>
  )
}
