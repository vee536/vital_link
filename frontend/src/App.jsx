import React, { useState } from 'react'
import Sidebar from './components/Sidebar'
import ConnectionBanner from './components/ConnectionBanner'
import DashboardPage from './pages/DashboardPage'
import PlaceholderPage from './components/PlaceholderPage'
import { useWebSocket } from './hooks/useWebSocket'

const PAGE_TITLES = {
  ambulance: 'Ambulance Input',
  triage: 'Triage',
  hospitals: 'Hospitals',
  'ai-triage': 'AI Triage',
}

export default function App() {
  const [activePage, setActivePage] = useState('dashboard')
<<<<<<< HEAD
  const { ambulances, status, reconnectCount } = useWebSocket()

  const ambulanceCount = ambulances.length
=======
  const { ambulances, ambulanceCount, status, reconnectCount } = useWebSocket()
>>>>>>> 7d91392ca5dc49f7677fd438c56bf03998a75c25

  return (
    <div className="flex h-screen overflow-hidden bg-[#0a0a0f] text-gray-100">
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        connectionStatus={status}
        ambulanceCount={ambulanceCount}   // ✅ live count from map
      />

      <main className="flex flex-col flex-1 min-w-0 overflow-hidden">
        <ConnectionBanner status={status} reconnectCount={reconnectCount} />

        {activePage === 'dashboard' ? (
          <DashboardPage
            ambulances={ambulances}         // ✅ pass full map
            ambulanceCount={ambulanceCount}
            status={status}
          />
        ) : (
          <PlaceholderPage title={PAGE_TITLES[activePage] || activePage} />
        )}
      </main>
    </div>
  )
}
