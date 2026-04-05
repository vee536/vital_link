import React, { useRef, useEffect } from 'react'
import { isAbnormal } from '../utils/vitals'

export default function VitalStat({ label, value, unit, vitalKey, icon }) {
  const abnormal = isAbnormal(vitalKey, value)
  const prevValueRef = useRef(value)
  const cellRef = useRef(null)

  useEffect(() => {
    if (prevValueRef.current !== value && cellRef.current) {
      cellRef.current.classList.remove('vital-flash')
      // Force reflow
      void cellRef.current.offsetWidth
      cellRef.current.classList.add('vital-flash')
    }
    prevValueRef.current = value
  }, [value])

  return (
    <div
      ref={cellRef}
      className={`rounded-lg px-3 py-2.5 border transition-colors duration-300 ${
        abnormal
          ? 'bg-red-950/40 border-red-800/60'
          : 'bg-[#0f0f18] border-[#1a1a28]'
      }`}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-mono text-gray-500 uppercase tracking-widest">{label}</span>
        {abnormal && (
          <span className="text-[9px] font-bold text-red-400 bg-red-900/40 px-1.5 py-0.5 rounded font-mono">
            !!
          </span>
        )}
      </div>
      <div className={`text-base font-bold font-mono leading-none ${abnormal ? 'text-red-300' : 'text-white'}`}>
        {value ?? '—'}
        {unit && <span className="text-xs font-normal text-gray-500 ml-1">{unit}</span>}
      </div>
    </div>
  )
}
