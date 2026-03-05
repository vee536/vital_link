import React, { useMemo } from 'react'
import AmbulanceCard from '../components/AmbulanceCard'
import EmptyState from '../components/EmptyState'

export default function DashboardPage({ ambulances, status }) {
  // Sort: High first, then Medium, then others; within same priority sort by most recent
const sorted = useMemo(() => {
  if (!ambulances) return []

  const values = Array.isArray(ambulances)
    ? ambulances
    : Object.values(ambulances)

  return values.sort((a, b) => {
    return new Date(b.timestamp || 0) - new Date(a.timestamp || 0)
  })
}, [ambulances])

const highCount = 0   // backend does not send priority
const inProgressCount = 0  // backend does not send status

  return (
    <div className="flex flex-col flex-1 min-h-0">
      {/* Page header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-[#1a1a28]">
        <div>
          <h1 className="text-xl font-bold text-white tracking-tight">Emergency Cases</h1>
          <p className="text-xs text-gray-500 mt-0.5 font-mono">Real-time incoming ambulance feed</p>
        </div>
        <div className="flex items-center gap-3">
          {highCount > 0 && (
            <div className="flex items-center gap-1.5 bg-red-900/30 border border-red-800/50 rounded-lg px-3 py-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
              <span className="text-xs font-bold text-red-400 font-mono">{highCount} HIGH</span>
            </div>
          )}
          <div className="flex items-center gap-1.5 bg-[#111118] border border-[#1a1a28] rounded-lg px-3 py-1.5">
            <span className="text-xs text-gray-500 font-mono">{inProgressCount} in progress</span>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {sorted.length === 0 ? (
          <EmptyState status={status} />
        ) : (
          <div className="space-y-4 max-w-6xl">
            {sorted.map((ambulance) => (
              <AmbulanceCard
                key={ambulance.timestamp}
                data={ambulance}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
