import React from 'react'

export default function EmptyState({ status }) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 py-24 text-center">
      <div className="w-16 h-16 rounded-2xl bg-[#1a1a28] border border-[#252535] flex items-center justify-center mb-5">
        <svg className="w-8 h-8 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </div>
      <h3 className="text-base font-semibold text-gray-400 mb-1">No Active Ambulances</h3>
      <p className="text-sm text-gray-600 max-w-xs">
        {status === 'connected'
          ? 'Waiting for incoming units. Cards will appear automatically when data arrives.'
          : 'Connecting to the live stream…'}
      </p>
      {status === 'connected' && (
        <div className="mt-4 flex items-center gap-2 text-xs font-mono text-green-500">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse-slow" />
          Stream connected
        </div>
      )}
    </div>
  )
}
