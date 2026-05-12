'use client'

import { useState, useRef } from 'react'

interface DataPoint {
  date: string
  amount: number
}

interface AreaChartProps {
  data: DataPoint[]
  color?: string
  currencySymbol?: string
  height?: number
}

export default function AreaChart({
  data,
  color = '#6366f1',
  currencySymbol = '$',
  height = 160,
}: AreaChartProps) {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; point: DataPoint } | null>(null)
  const svgRef = useRef<SVGSVGElement>(null)

  if (!data.length) return null

  const padL = 8, padR = 8, padT = 16, padB = 8
  const vw = 500
  const vh = height
  const chartW = vw - padL - padR
  const chartH = vh - padT - padB

  const maxVal = Math.max(...data.map(d => d.amount), 1)
  const minVal = 0

  function px(i: number) { return padL + (i / (data.length - 1)) * chartW }
  function py(v: number) { return padT + chartH - ((v - minVal) / (maxVal - minVal)) * chartH }

  // Build smooth bezier path
  function buildPath(pts: { x: number; y: number }[]): string {
    if (pts.length < 2) return `M ${pts[0].x} ${pts[0].y}`
    let d = `M ${pts[0].x} ${pts[0].y}`
    for (let i = 1; i < pts.length; i++) {
      const prev = pts[i - 1]
      const curr = pts[i]
      const cpx = (prev.x + curr.x) / 2
      d += ` C ${cpx} ${prev.y} ${cpx} ${curr.y} ${curr.x} ${curr.y}`
    }
    return d
  }

  const points = data.map((d, i) => ({ x: px(i), y: py(d.amount), ...d }))
  const linePath = buildPath(points)
  const areaPath = `${linePath} L ${points[points.length - 1].x} ${padT + chartH} L ${points[0].x} ${padT + chartH} Z`

  const gradId = `area-grad-${color.replace('#', '')}`

  function handleMouseMove(e: React.MouseEvent<SVGSVGElement>) {
    const rect = svgRef.current!.getBoundingClientRect()
    const relX = ((e.clientX - rect.left) / rect.width) * vw - padL
    const idx = Math.round((relX / chartW) * (data.length - 1))
    const clamped = Math.max(0, Math.min(data.length - 1, idx))
    setTooltip({ x: points[clamped].x, y: points[clamped].y, point: data[clamped] })
  }

  const formatDate = (d: string) => {
    const dt = new Date(d)
    return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  return (
    <div className="relative w-full">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${vw} ${vh}`}
        style={{ height }}
        className="w-full"
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setTooltip(null)}
      >
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>

        {/* Area fill */}
        <path d={areaPath} fill={`url(#${gradId})`} />

        {/* Line */}
        <path d={linePath} fill="none" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />

        {/* Hover elements */}
        {tooltip && (
          <>
            <line
              x1={tooltip.x} y1={padT} x2={tooltip.x} y2={padT + chartH}
              stroke={color} strokeWidth={1} strokeDasharray="4 3" opacity={0.5}
            />
            <circle cx={tooltip.x} cy={tooltip.y} r={5} fill={color} stroke="#090912" strokeWidth={2} />
            <circle cx={tooltip.x} cy={tooltip.y} r={8} fill={color} opacity={0.2} />
          </>
        )}
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div
          className="absolute pointer-events-none z-10 bg-[#1a1a2e] border border-[#2d2d3d] rounded-xl px-3 py-2 shadow-xl text-xs"
          style={{
            left: `${(tooltip.x / vw) * 100}%`,
            bottom: '100%',
            transform: 'translateX(-50%)',
            marginBottom: 8,
          }}
        >
          <div className="text-slate-400">{formatDate(tooltip.point.date)}</div>
          <div className="font-semibold text-white">
            {currencySymbol}{tooltip.point.amount.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>
      )}
    </div>
  )
}
