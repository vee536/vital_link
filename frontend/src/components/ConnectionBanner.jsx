import React from 'react'

export default function ConnectionBanner({ status, reconnectCount }) {
  if (status === 'connected') return null

  const isReconnecting = status === 'reconnecting'

  return (
    <div className={`flex items-center gap-3 px-4 py-2.5 text-sm font-mono border-b ${
      isReconnecting
        ? 'bg-yellow-950/40 border-yellow-900/40 text-yellow-400'
        : 'bg-red-950/40 border-red-900/40 text-red-400'
    }`}>
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
        isReconnecting ? 'bg-yellow-400 animate-pulse' : 'bg-red-500'
      }`} />
      {isReconnecting
        ? `Reconnecting to live stream… (attempt ${reconnectCount})`
        : 'WebSocket disconnected — live updates paused'}
    </div>
  )
}
