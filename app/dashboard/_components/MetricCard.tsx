'use client'

interface MetricCardProps {
  label: string
  value: string
  change?: number
  changeLabel?: string
  icon: React.ReactNode
  iconBg: string
  trend?: 'up' | 'down' | 'flat'
  positive?: boolean
}

export default function MetricCard({
  label,
  value,
  change,
  changeLabel = 'vs last month',
  icon,
  iconBg,
  trend = 'flat',
  positive,
}: MetricCardProps) {
  const isPositive = positive !== undefined ? positive : trend === 'up'

  return (
    <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5 hover:border-[#2d2d3d] transition-colors">
      <div className="flex items-start justify-between mb-4">
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${iconBg}`}>
          {icon}
        </div>
        {change !== undefined && (
          <div className={`flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-lg ${
            isPositive
              ? 'text-emerald-400 bg-emerald-500/10'
              : 'text-red-400 bg-red-500/10'
          }`}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} className={`w-3 h-3 ${isPositive ? '' : 'rotate-180'}`}>
              <path d="M18 15l-6-6-6 6" />
            </svg>
            {Math.abs(change).toFixed(1)}%
          </div>
        )}
      </div>
      <div className="text-2xl font-bold text-white tracking-tight mb-1">{value}</div>
      <div className="text-sm text-slate-500">{label}</div>
      {changeLabel && change !== undefined && (
        <div className="text-xs text-slate-600 mt-1">{changeLabel}</div>
      )}
    </div>
  )
}
