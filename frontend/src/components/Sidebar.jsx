import React from 'react'

const NAV_ITEMS = [
  {
    id: 'dashboard',
    label: 'Dashboard',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    ),
  },
  {
    id: 'ambulance',
    label: 'Ambulance Input',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M13 10V3L4 14h7v7l9-11h-7z" />
      </svg>
    ),
  },
  {
    id: 'triage',
    label: 'Triage',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z" />
      </svg>
    ),
  },
  {
    id: 'hospitals',
    label: 'Hospitals',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    ),
  },
  {
    id: 'ai-triage',
    label: 'AI Triage',
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
          d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
  },
]

export default function Sidebar({ activePage, onNavigate, connectionStatus, ambulanceCount }) {
  const isConnected = connectionStatus === 'connected'
  const isReconnecting = connectionStatus === 'reconnecting'

  return (
    <aside className="flex flex-col w-56 min-h-screen bg-[#0d0d14] border-r border-[#1a1a28] flex-shrink-0">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-5 border-b border-[#1a1a28]">
        <div className="w-8 h-8 rounded-lg bg-red-700 flex items-center justify-center flex-shrink-0">
          <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 14H9V8h2v8zm4 0h-2V8h2v8z" />
            <path d="M13 7h-2v2h-2v2h2v2h2v-2h2v-2h-2z" />
          </svg>
        </div>
        <div>
          <div className="text-sm font-bold text-white tracking-wide">VitalLink</div>
          <div className="text-[10px] text-gray-500 font-mono uppercase tracking-widest">Emergency System</div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        <div className="text-[10px] font-semibold text-gray-600 uppercase tracking-widest px-2 mb-2">
          Navigation
        </div>
        {NAV_ITEMS.map((item) => {
          const isActive = activePage === item.id
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`
                w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-150 text-left
                ${isActive
                  ? 'bg-red-900/30 text-red-400 border border-red-900/50'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
                }
              `}
            >
              <span className={isActive ? 'text-red-400' : 'text-gray-500'}>{item.icon}</span>
              {item.label}
            </button>
          )
        })}
      </nav>

      {/* Status panel */}
      <div className="px-3 pb-5 space-y-2">
        {/* Active ambulances count */}
        <div className="bg-[#111118] border border-[#1a1a28] rounded-lg px-3 py-2.5">
          <div className="text-[10px] text-gray-600 uppercase tracking-widest font-mono mb-1">Active Units</div>
          <div className="text-2xl font-bold text-white font-mono">{ambulanceCount}</div>
        </div>

        {/* Connection status */}
        <div className={`rounded-lg px-3 py-2.5 border flex items-center gap-2.5 ${
          isConnected
            ? 'bg-green-900/20 border-green-900/40'
            : isReconnecting
            ? 'bg-yellow-900/20 border-yellow-900/40'
            : 'bg-red-900/20 border-red-900/40'
        }`}>
          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
            isConnected
              ? 'bg-green-400 shadow-[0_0_6px_rgba(74,222,128,0.8)] animate-pulse-slow'
              : isReconnecting
              ? 'bg-yellow-400 animate-pulse'
              : 'bg-red-500'
          }`} />
          <div>
            <div className={`text-xs font-semibold ${
              isConnected ? 'text-green-400' : isReconnecting ? 'text-yellow-400' : 'text-red-400'
            }`}>
              {isConnected ? 'Live' : isReconnecting ? 'Reconnecting…' : 'Disconnected'}
            </div>
            <div className="text-[10px] text-gray-600 font-mono">WebSocket</div>
          </div>
        </div>
      </div>
    </aside>
  )
}
