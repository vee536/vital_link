import React from 'react'
import VitalStat from './VitalStat'
import { priorityConfig, statusConfig, formatTimestamp } from '../utils/vitals'

export default function AmbulanceCard({ data }) {
  const ambulance_id = data?.ambulance_id ?? 'AMB-001'
  const case_id = data?.case_id ?? null
  const patient_name = data?.patient?.name ?? 'Unknown Patient'
  const age = data?.patient?.age ?? null
  const condition = data?.patient?.condition ?? '—'
  const vitals = data?.vitals ?? {}
  const alerts = data?.alerts ?? []
  const ai = data?.ai ?? null
  const timestamp = data?.timestamp

  // Derive priority from AI severity
  const severityLower = ai?.severity?.toLowerCase()
  const priority = severityLower === 'critical' ? 'high'
    : severityLower === 'warning' ? 'medium'
    : 'low'

  const status = data?.status ?? 'in progress'
  const pc = priorityConfig(priority)
  const sc = statusConfig(status)

  const icuPct = ai?.icu_probability > 0
    ? Math.round(ai.icu_probability * 100)
    : null

  const actions = ai?.actions ?? []

  return (
    <div className={`
      relative bg-[#111118] rounded-xl border border-[#1e1e2e]
      border-l-4 ${pc.cardBorder}
      animate-fade-in overflow-hidden
    `}>

      {/* Header */}
      <div className="flex items-start justify-between px-4 pt-4 pb-3 border-b border-[#1a1a28]">
        <div className="flex items-start gap-3 min-w-0">
          <div className={`mt-0.5 w-2.5 h-2.5 rounded-full flex-shrink-0 ${pc.dot} shadow-sm`} />
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-base font-semibold text-white leading-tight">{patient_name}</h3>
              {age && <span className="text-xs text-gray-500 font-mono">Age {age}</span>}
            </div>
            <div className="mt-0.5 text-sm text-gray-400">{condition}</div>
          </div>
        </div>

        <div className="flex flex-col items-end gap-1.5 flex-shrink-0 ml-3">
          <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded border ${pc.bg} ${pc.text} ${pc.border}`}>
            {pc.label}
          </span>
          <span className={`text-[10px] font-medium px-2 py-0.5 rounded border ${sc.bg} ${sc.text} ${sc.border}`}>
            {sc.label}
          </span>

          {/* AI Condition + Severity */}
          {ai && (
            <span className={`text-[10px] font-bold font-mono px-2 py-0.5 rounded border ${
              severityLower === 'critical'
                ? 'bg-red-950/60 text-red-400 border-red-800'
                : severityLower === 'warning'
                ? 'bg-yellow-950/60 text-yellow-400 border-yellow-800'
                : 'bg-green-950/60 text-green-400 border-green-800'
            }`}>
              {ai.condition ?? 'Unknown'} — {ai.severity?.toUpperCase() ?? '?'}
            </span>
          )}

          {/* Confidence */}
          {ai?.confidence > 0 && (
            <span className="text-[10px] font-mono text-gray-500">
              {ai.confidence}% confident
            </span>
          )}

          {/* ICU Probability */}
          {icuPct !== null && (
            <span className={`text-[10px] font-mono ${icuPct >= 70 ? 'text-red-400' : icuPct >= 40 ? 'text-yellow-400' : 'text-gray-500'}`}>
              ICU {icuPct}%
            </span>
          )}
        </div>
      </div>

      {/* Meta row */}
      <div className="flex items-center gap-4 px-4 py-2 bg-[#0d0d14]/60 border-b border-[#1a1a28]">
        <div className="flex items-center gap-1.5 text-[11px] font-mono text-gray-500">
          <svg className="w-3 h-3 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          {ambulance_id}
        </div>
        {case_id && <div className="text-[11px] font-mono text-gray-600">Case #{case_id}</div>}
        <div className="ml-auto text-[11px] font-mono text-gray-600">{formatTimestamp(timestamp)}</div>
      </div>

      {/* Vitals */}
      <div className="px-4 py-3">
        <div className="text-[10px] font-mono text-gray-600 uppercase tracking-widest mb-2">Vitals</div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-2">
          <VitalStat label="HR" value={vitals.heart_rate} unit="bpm" vitalKey="heart_rate" />
          <VitalStat label="SpO₂" value={vitals.spo2} unit="%" vitalKey="spo2" />
          <VitalStat
            label="BP"
            value={vitals.bp_sys != null && vitals.bp_dia != null ? `${vitals.bp_sys}/${vitals.bp_dia}` : null}
            unit="mmHg"
            vitalKey="bp_sys"
          />
          <VitalStat label="Temp" value={vitals.temperature} unit="°C" vitalKey="temperature" />
          <div className="rounded-lg px-3 py-2.5 border bg-[#0f0f18] border-[#1a1a28]">
            <div className="text-[10px] font-mono text-gray-500 uppercase tracking-widest mb-1">Resp</div>
            <div className="text-base font-bold font-mono text-white leading-none">
              {vitals.respiratory_rate ?? <span className="text-gray-600">—</span>}
              {vitals.respiratory_rate && <span className="text-xs font-normal text-gray-500 ml-1">/min</span>}
            </div>
          </div>
        </div>
      </div>

      {/* Recommended Actions */}
      {actions.length > 0 && (
        <div className="px-4 pb-3">
          <div className="text-[10px] font-mono text-gray-600 uppercase tracking-widest mb-1.5">
            Recommended Actions
          </div>
          <div className="flex flex-wrap gap-1.5">
            {actions.map((action, i) => (
              <span
                key={i}
                className="text-[11px] font-mono text-blue-300 bg-blue-950/40 border border-blue-800/50 px-2 py-0.5 rounded"
              >
                → {action}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Alerts */}
      {alerts.length > 0 && (
        <div className="px-4 pb-4">
          <div className="flex items-center gap-2 flex-wrap">
            <svg className="w-3 h-3 text-red-500 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            {alerts.map((alert, i) => (
              <span key={i} className="text-[11px] font-mono font-semibold text-red-400 bg-red-950/50 border border-red-900/50 px-2 py-0.5 rounded">
                {alert}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}