import React from 'react'

export default function PlaceholderPage({ title }) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 py-24">
      <div className="w-14 h-14 rounded-xl bg-[#1a1a28] border border-[#252535] flex items-center justify-center mb-4">
        <svg className="w-6 h-6 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
        </svg>
      </div>
      <h2 className="text-lg font-semibold text-gray-400 mb-1">{title}</h2>
      <p className="text-sm text-gray-600">This section is under construction.</p>
    </div>
  )
}
