'use client'

import { useState } from 'react'

interface DonutSlice {
  label: string
  value: number
  color: string
  icon?: string
}

interface DonutChartProps {
  data: DonutSlice[]
  currencySymbol?: string
  size?: number
}

function polarToXY(cx: number, cy: number, r: number, angleDeg: number) {
  const rad = ((angleDeg - 90) * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

function describeArc(cx: number, cy: number, r: number, startAngle: number, endAngle: number) {
  const start = polarToXY(cx, cy, r, endAngle)
  const end = polarToXY(cx, cy, r, startAngle)
  const largeArc = endAngle - startAngle > 180 ? 1 : 0
  return `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 0 ${end.x} ${end.y}`
}

export default function DonutChart({ data, currencySymbol = '$', size = 220 }: DonutChartProps) {
  const [hovered, setHovered] = useState<number | null>(null)

  const total = data.reduce((s, d) => s + d.value, 0)
  if (!total) return null

  const cx = size / 2, cy = size / 2
  const outerR = size / 2 - 16
  const innerR = outerR * 0.6
  const strokeW = outerR - innerR

  let cumAngle = 0
  const slices = data.map((d, i) => {
    const angle = (d.value / total) * 360
    const start = cumAngle
    cumAngle += angle
    return { ...d, startAngle: start, endAngle: cumAngle, angle, index: i }
  })

  const active = hovered !== null ? slices[hovered] : null

  return (
    <div className="flex flex-col items-center gap-4">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} style={{ overflow: 'visible' }}>
          <defs>
            {slices.map(s => (
              <filter key={s.index} id={`glow-${s.index}`}>
                <feGaussianBlur stdDeviation="3" result="coloredBlur" />
                <feMerge><feMergeNode in="coloredBlur" /><feMergeNode in="SourceGraphic" /></feMerge>
              </filter>
            ))}
          </defs>
          {slices.map(s => {
            const isActive = hovered === s.index
            const r = isActive ? outerR + 4 : outerR
            const arc = describeArc(cx, cy, r, s.startAngle, s.endAngle)
            return (
              <path
                key={s.index}
                d={arc}
                fill="none"
                stroke={s.color}
                strokeWidth={isActive ? strokeW + 6 : strokeW}
                strokeLinecap="round"
                opacity={hovered !== null && !isActive ? 0.35 : 0.9}
                filter={isActive ? `url(#glow-${s.index})` : undefined}
                className="transition-all duration-200 cursor-pointer"
                onMouseEnter={() => setHovered(s.index)}
                onMouseLeave={() => setHovered(null)}
              />
            )
          })}

          {/* Center text */}
          <text x={cx} y={cy - 10} textAnchor="middle" fontSize={11} fill="#64748b">
            {active ? active.label : 'Total'}
          </text>
          <text x={cx} y={cy + 14} textAnchor="middle" fontSize={20} fontWeight="700" fill="white">
            {currencySymbol}{active
              ? active.value >= 1000 ? `${(active.value / 1000).toFixed(1)}k` : active.value.toFixed(0)
              : total >= 1000 ? `${(total / 1000).toFixed(1)}k` : total.toFixed(0)
            }
          </text>
          {active && (
            <text x={cx} y={cy + 30} textAnchor="middle" fontSize={11} fill="#64748b">
              {((active.value / total) * 100).toFixed(1)}%
            </text>
          )}
        </svg>
      </div>

      {/* Legend */}
      <div className="w-full space-y-2">
        {slices.map(s => (
          <div
            key={s.index}
            className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg cursor-pointer transition-colors"
            style={{ background: hovered === s.index ? `${s.color}15` : 'transparent' }}
            onMouseEnter={() => setHovered(s.index)}
            onMouseLeave={() => setHovered(null)}
          >
            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: s.color }} />
            <span className="text-xs text-slate-400 flex-1 truncate">{s.icon} {s.label}</span>
            <span className="text-xs font-semibold text-slate-300">{currencySymbol}{s.value.toLocaleString()}</span>
            <span className="text-[10px] text-slate-600 w-10 text-right">
              {((s.value / total) * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
