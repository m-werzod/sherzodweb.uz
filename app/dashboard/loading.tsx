export default function DashboardLoading() {
  return (
    <div className="p-6 lg:p-8 max-w-7xl animate-pulse">
      {/* Header skeleton */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <div className="h-7 w-32 bg-[#1e1e2e] rounded-lg mb-2" />
          <div className="h-4 w-24 bg-[#1a1a2a] rounded-md" />
        </div>
        <div className="h-10 w-36 bg-[#1e1e2e] rounded-xl" />
      </div>

      {/* Metric cards skeleton */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-5">
            <div className="flex items-start justify-between mb-4">
              <div className="w-10 h-10 rounded-xl bg-[#1e1e2e]" />
              <div className="h-6 w-14 bg-[#1e1e2e] rounded-lg" />
            </div>
            <div className="h-7 w-28 bg-[#1e1e2e] rounded-lg mb-2" />
            <div className="h-3 w-20 bg-[#1a1a2a] rounded-md" />
          </div>
        ))}
      </div>

      {/* Charts skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
        <div className="lg:col-span-2 bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
          <div className="h-5 w-48 bg-[#1e1e2e] rounded-lg mb-5" />
          <div className="h-40 bg-[#1a1a2a] rounded-xl" />
        </div>
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
          <div className="h-5 w-24 bg-[#1e1e2e] rounded-lg mb-4" />
          <div className="space-y-3">
            {[1,2,3,4,5].map(i => <div key={i} className="h-10 bg-[#1a1a2a] rounded-xl" />)}
          </div>
        </div>
      </div>

      {/* Bottom grid skeleton */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
          <div className="h-5 w-40 bg-[#1e1e2e] rounded-lg mb-5" />
          <div className="space-y-3">
            {[1,2,3,4,5].map(i => (
              <div key={i} className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-[#1e1e2e]" />
                <div className="flex-1">
                  <div className="h-4 w-40 bg-[#1e1e2e] rounded-md mb-1.5" />
                  <div className="h-3 w-24 bg-[#1a1a2a] rounded-md" />
                </div>
                <div className="h-4 w-20 bg-[#1e1e2e] rounded-md" />
              </div>
            ))}
          </div>
        </div>
        <div className="bg-[#0e0e18] border border-[#1e1e2e] rounded-2xl p-6">
          <div className="h-5 w-32 bg-[#1e1e2e] rounded-lg mb-5" />
          <div className="space-y-4">
            {[1,2,3].map(i => (
              <div key={i}>
                <div className="flex justify-between mb-1.5">
                  <div className="h-3 w-20 bg-[#1e1e2e] rounded-md" />
                  <div className="h-3 w-16 bg-[#1e1e2e] rounded-md" />
                </div>
                <div className="h-1.5 bg-[#1e1e2e] rounded-full" />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
