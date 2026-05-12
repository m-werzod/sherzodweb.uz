'use client'

import { useState } from 'react'

interface BarData {
  label: string
  income: number
  expenses: number
}

interface BarChartProps {
  data: BarData[]
  currencySymbol?: string
  height?: number
}

export default function BarChart({ data, currencySymbol = '$', height = 200 }: BarChartProps) {
  const [tooltip, setTooltip] = useState<{ x: number; y: number; d: BarData } | null>(null)

  if (!data.length) return null

  const maxVal = Math.max(...data.flatMap(d => [d.income, d.expenses]), 1)
  const padL = 52, padR = 12, padT = 16, padB = 36
  const w = 520
  const h = height
  const chartW = w - padL - padR
  const chartH = h - padT - padB
  const groupW = chartW / data.length
  const barW = Math.min((groupW - 12) / 2, 28)
  const gap = 4

  const yTicks = [0, 0.25, 0.5, 0.75, 1].map(r => ({
    val: maxVal * r,
    y: padT + chartH * (1 - r),
  }))

  function barY(val: number) {
    return padT + chartH - (val / maxVal) * chartH
  }
  function barH(val: number) {
    return (val / maxVal) * chartH
  }

  return (
    <div className="relative w-full" style={{ maxWidth: '100%' }}>
      <svg
        viewBox={`0 0 ${w} ${h}`}
        className="w-full"
        onMouseLeave={() => setTooltip(null)}
        style={{ height }}
      >
        {/* Grid lines */}
        {yTicks.map(t => (
          <g key={t.val}>
            <line x1={padL} y1={t.y} x2={w - padR} y2={t.y} stroke="#1e1e2e" strokeWidth={1} />
            <text x={padL - 8} y={t.y + 4} textAnchor="end" fontSize={10} fill="#475569">
              {t.val >= 1000 ? `${currencySymbol}${(t.val / 1000).toFixed(0)}k` : `${currencySymbol}${t.val.toFixed(0)}`}
            </text>
          </g>
        ))}

        {/* Bars */}
        {data.map((d, i) => {
          const cx = padL + i * groupW + groupW / 2
          const incX = cx - gap / 2 - barW
          const expX = cx + gap / 2

          return (
            <g key={i}
              onMouseEnter={e => {
                const rect = (e.target as SVGElement).closest('svg')!.getBoundingClientRect()
                setTooltip({ x: cx, y: barY(Math.max(d.income, d.expenses)), d })
              }}
            >
              {/* Income bar */}
              <rect
                x={incX} y={barY(d.income)} width={barW} height={Math.max(barH(d.income), 0)}
                rx={3} fill="#6366f1" opacity={0.85}
                className="transition-opacity duration-150 hover:opacity-100"
              />
              {/* Expense bar */}
              <rect
                x={expX} y={barY(d.expenses)} width={barW} height={Math.max(barH(d.expenses), 0)}
                rx={3} fill="#ef4444" opacity={0.75}
                className="transition-opacity duration-150 hover:opacity-100"
              />
              {/* X label */}
              <text x={cx} y={h - 8} textAnchor="middle" fontSize={10} fill="#475569">
                {d.label}
              </text>
            </g>
          )
        })}

        {/* Axis line */}
        <line x1={padL} y1={padT + chartH} x2={w - padR} y2={padT + chartH} stroke="#1e1e2e" strokeWidth={1} />
      </svg>

      {/* Tooltip */}
      {tooltip && (
        <div className="absolute pointer-events-none z-10 bg-[#1a1a2e] border border-[#2d2d3d] rounded-xl px-3 py-2.5 shadow-xl text-xs"
          style={{
            left: `${(tooltip.x / 520) * 100}%`,
            top: 0,
            transform: 'translateX(-50%)',
          }}>
          <div className="font-semibold text-white mb-1.5">{tooltip.d.label}</div>
          <div className="flex items-center gap-2 text-indigo-400">
            <span className="w-2 h-2 rounded-full bg-indigo-500 inline-block" />
            Income: {currencySymbol}{tooltip.d.income.toLocaleString()}
          </div>
          <div className="flex items-center gap-2 text-red-400 mt-0.5">
            <span className="w-2 h-2 rounded-full bg-red-500 inline-block" />
            Expenses: {currencySymbol}{tooltip.d.expenses.toLocaleString()}
          </div>
        </div>
      )}

      {/* Legend */}
      <div className="flex items-center gap-4 justify-center mt-2">
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <span className="w-3 h-3 rounded bg-indigo-500/80 inline-block" /> Income
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-400">
          <span className="w-3 h-3 rounded bg-red-500/75 inline-block" /> Expenses
        </div>
      </div>
    </div>
  )
}
