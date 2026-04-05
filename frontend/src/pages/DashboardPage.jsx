import React, { useEffect, useRef } from 'react'
import EmptyState from '../components/EmptyState'

function fmt(val, fallback = '—') {
  if (val === null || val === undefined || val === '') return fallback
  return val
}

function useFlash(value, ref) {
  const prev = useRef(value)
  useEffect(() => {
    if (prev.current !== value && ref.current) {
      ref.current.classList.remove('vital-flash')
      void ref.current.offsetWidth
      ref.current.classList.add('vital-flash')
    }
    prev.current = value
  }, [value, ref])
}

function VitalTile({ label, value, unit, alert = false, wide = false }) {
  const ref = useRef(null)
  useFlash(value, ref)

  return (
    <div
      ref={ref}
      className={`
        flex flex-col justify-between rounded-xl border px-5 py-4 transition-colors duration-300
        ${wide ? 'col-span-2' : ''}
        ${alert ? 'bg-red-950/40 border-red-700/60' : 'bg-[#0e0e18] border-[#1a1a2e]'}
      `}
    >
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-bold tracking-widest text-gray-500 font-mono uppercase">
          {label}
        </span>
        {alert && (
          <span className="text-[9px] font-bold text-red-400 font-mono tracking-wider animate-pulse">!!</span>
        )}
      </div>
      <div className="flex items-end gap-1.5">
        <span className={`text-3xl font-bold font-mono tabular-nums leading-none ${alert ? 'text-red-400' : 'text-white'}`}>
          {fmt(value)}
        </span>
        {unit && <span className="text-xs text-gray-500 font-mono mb-0.5">{unit}</span>}
      </div>
    </div>
  )
}

function AlertBadge({ text }) {
  return (
    <span className="inline-flex items-center gap-1.5 bg-red-900/30 border border-red-700/50 text-red-400 text-xs font-mono font-semibold px-3 py-1 rounded-full">
      <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
      {text}
    </span>
  )
}

function AmbulanceCard({ data }) {
  const { ambulance_id, patient = {}, vitals = {}, alerts = [], timestamp } = data

  const hr    = vitals.heart_rate       ?? vitals.hr   ?? null
  const spo2  = vitals.spo2             ?? vitals.SpO2 ?? null
  const temp  = vitals.temperature      ?? vitals.temp ?? null
  const resp  = vitals.respiratory_rate ?? vitals.resp ?? null
  const bpSys = vitals.bp_sys           ?? vitals.systolic_bp  ?? vitals.bp_systolic  ?? null
  const bpDia = vitals.bp_dia           ?? vitals.diastolic_bp ?? vitals.bp_diastolic ?? null
  const bp    = bpSys && bpDia ? `${bpSys}/${bpDia}` : (vitals.bp ?? null)

  const ai       = data.ai ?? null
  const condition = ai?.condition ?? null
  const severity  = ai?.severity  ?? null
  const confidence = ai?.confidence ?? null
  const actions   = ai?.actions ?? []
  const icuProb   = ai?.icu_probability ?? null

  const severityColor =
    severity?.toLowerCase() === 'critical' ? 'text-red-400' :
    severity?.toLowerCase() === 'warning'  ? 'text-yellow-400' :
    'text-emerald-400'

  const alertTexts = Array.isArray(alerts) ? alerts.map(a =>
    typeof a === 'string' ? a : (a.message || a.type || JSON.stringify(a))
  ) : []

  const hrAlert   = alertTexts.some(t => /heart|hr|cardiac|bradycardia|tachycardia/i.test(t))
  const spo2Alert = alertTexts.some(t => /oxygen|spo2|saturation/i.test(t))
  const bpAlert   = alertTexts.some(t => /blood.?pressure|bp|systolic|diastolic/i.test(t))
  const tempAlert = alertTexts.some(t => /temp|fever|hypothermia/i.test(t))
  const respAlert = alertTexts.some(t => /resp|breathing/i.test(t))

  const timeStr = timestamp
    ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null

  const hasAlerts = alertTexts.length > 0 || severity?.toLowerCase() === 'critical'

  return (
    <div className="rounded-2xl border border-[#1a1a2e] bg-[#0b0b14] overflow-hidden shadow-2xl">
      <div className={`flex items-center justify-between px-6 py-4 border-b border-[#1a1a2e] ${hasAlerts ? 'bg-red-950/20' : 'bg-[#0d0d1a]'}`}>
        <div className="flex items-center gap-3">
          <span className="relative flex h-2.5 w-2.5">
            <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${hasAlerts ? 'bg-red-400' : 'bg-emerald-400'}`} />
            <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${hasAlerts ? 'bg-red-500' : 'bg-emerald-500'}`} />
          </span>
          <div>
            <p className="text-[10px] font-bold tracking-widest text-gray-500 font-mono uppercase">
              Ambulance {ambulance_id} · AMB-{ambulance_id}
            </p>
            <p className="text-sm font-semibold text-gray-300 mt-0.5">NIMHANS Hospital</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {timeStr && <span className="text-xs text-gray-600 font-mono">{timeStr}</span>}
          {hasAlerts ? (
            <span className="text-[10px] font-bold tracking-widest text-red-400 font-mono bg-red-900/20 border border-red-800/40 px-2.5 py-1 rounded-full uppercase animate-pulse">Alert</span>
          ) : (
            <span className="text-[10px] font-bold tracking-widest text-emerald-400 font-mono bg-emerald-900/20 border border-emerald-800/40 px-2.5 py-1 rounded-full uppercase">Live</span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-6 px-6 py-3 border-b border-[#1a1a2e] bg-[#0c0c16]">
        <div>
          <p className="text-[10px] text-gray-600 font-mono uppercase tracking-wider">Patient</p>
          <p className="text-sm font-bold text-white mt-0.5">
            {fmt(patient.name)}
            {patient.age ? <span className="text-gray-500 font-normal ml-2">Age {patient.age}</span> : null}
          </p>
        </div>
        {patient.id && (
          <div>
            <p className="text-[10px] text-gray-600 font-mono uppercase tracking-wider">ID</p>
            <p className="text-sm font-mono text-gray-300 mt-0.5">{patient.id}</p>
          </div>
        )}
        {condition && (
          <div>
            <p className="text-[10px] text-gray-600 font-mono uppercase tracking-wider">AI Diagnosis</p>
            <p className={`text-sm font-bold font-mono mt-0.5 ${severityColor}`}>
              {condition} — {severity}
              {confidence != null && <span className="text-gray-500 font-normal ml-2">{confidence.toFixed(1)}%</span>}
            </p>
          </div>
        )}
        {icuProb != null && (
          <div>
            <p className="text-[10px] text-gray-600 font-mono uppercase tracking-wider">ICU Prob</p>
            <p className="text-sm font-bold font-mono text-orange-400 mt-0.5">{(icuProb * 100).toFixed(0)}%</p>
          </div>
        )}
      </div>

      <div className="px-6 pt-5 pb-4">
        <p className="text-[10px] font-bold tracking-widest text-gray-600 font-mono uppercase mb-3">Vitals</p>
        <div className="grid grid-cols-4 gap-3">
          <VitalTile label="HR"   value={hr}   unit="bpm"  alert={hrAlert} />
          <VitalTile label="SpO₂" value={spo2} unit="%"    alert={spo2Alert} />
          <VitalTile label="BP"   value={bp}   unit="mmHg" alert={bpAlert} />
          <VitalTile label="TEMP" value={temp} unit="°C"   alert={tempAlert} />
          {resp !== null && <VitalTile label="RESP" value={resp} unit="brpm" alert={respAlert} />}
        </div>
      </div>

      {actions.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 px-6 pb-4">
          <span className="text-[10px] text-gray-600 font-mono uppercase tracking-wider mr-1">Actions</span>
          {actions.map((a, i) => (
            <span key={i} className="inline-flex items-center bg-blue-900/30 border border-blue-700/50 text-blue-300 text-xs font-mono font-semibold px-3 py-1 rounded-full">
              {a}
            </span>
          ))}
        </div>
      )}

      {alertTexts.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 px-6 pb-5">
          <span className="text-[10px] text-gray-600 font-mono uppercase tracking-wider mr-1">▲</span>
          {alertTexts.map((text, i) => <AlertBadge key={i} text={text} />)}
        </div>
      )}
    </div>
  )
}

export default function DashboardPage({ ambulances, ambulanceCount, status }) {
  const ambulanceList = Object.values(ambulances || {})

  if (ambulanceList.length === 0) {
    return (
      <div className="flex flex-col flex-1 min-h-0">
        <PageHeader count={0} highCount={0} />
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <EmptyState status={status} />
        </div>
      </div>
    )
  }

  const sorted = ambulanceList.sort((a, b) =>
    String(a.ambulance_id || '').localeCompare(String(b.ambulance_id || ''))
  )
  const highCount = sorted.filter(a => a.ai?.severity?.toLowerCase() === 'critical').length

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <PageHeader count={sorted.length} highCount={highCount} />
      <div className="flex-1 overflow-y-auto px-6 py-6">
        <div className="max-w-3xl w-full mx-auto space-y-5">
          {sorted.map((data) => (
            <AmbulanceCard key={data.ambulance_id || 'UNKNOWN'} data={data} />
          ))}
        </div>
      </div>
    </div>
  )
}

function PageHeader({ count, highCount }) {
  return (
    <div className="flex items-center justify-between px-6 py-4 border-b border-[#1a1a28]">
      <div>
        <h1 className="text-xl font-bold text-white tracking-tight">Emergency Cases</h1>
        <p className="text-xs text-gray-500 mt-0.5 font-mono">Real-time incoming ambulance feed</p>
      </div>
      <div className="flex items-center gap-3">
        {highCount > 0 && (
          <div className="flex items-center gap-1.5 bg-red-900/20 border border-red-800/40 rounded-lg px-3 py-1.5">
            <span className="text-xs text-red-400 font-mono font-bold animate-pulse">{highCount} CRITICAL</span>
          </div>
        )}
        <div className="flex items-center gap-1.5 bg-[#111118] border border-[#1a1a28] rounded-lg px-3 py-1.5">
          <span className="text-xs text-gray-500 font-mono">
            {count === 0 ? '0 in progress' : `${count} active unit${count > 1 ? 's' : ''} in progress`}
          </span>
        </div>
      </div>
    </div>
  )
}