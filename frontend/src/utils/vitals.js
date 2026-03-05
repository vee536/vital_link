// Normal ranges for vitals
const RANGES = {
  heart_rate:  { min: 60,  max: 100 },
  spo2:        { min: 95,  max: 100 },
  bp_sys:      { min: 90,  max: 130 },
  bp_dia:      { min: 60,  max: 85  },
  temperature: { min: 36.1, max: 37.2 },
}

export function isAbnormal(key, value) {
  const range = RANGES[key]
  if (!range) return false
  return value < range.min || value > range.max
}

export function formatBP(sys, dia) {
  return `${sys}/${dia} mmHg`
}

export function priorityConfig(priority) {
  switch (priority?.toLowerCase()) {
    case 'high':
      return {
        label: 'HIGH',
        bg: 'bg-red-900/40',
        text: 'text-red-400',
        border: 'border-red-800/60',
        dot: 'bg-red-500',
        cardBorder: 'border-l-red-600',
      }
    case 'medium':
      return {
        label: 'MEDIUM',
        bg: 'bg-orange-900/40',
        text: 'text-orange-400',
        border: 'border-orange-800/60',
        dot: 'bg-orange-500',
        cardBorder: 'border-l-orange-500',
      }
    case 'low':
      return {
        label: 'LOW',
        bg: 'bg-green-900/30',
        text: 'text-green-400',
        border: 'border-green-800/60',
        dot: 'bg-green-500',
        cardBorder: 'border-l-green-500',
      }
    default:
      return {
        label: priority?.toUpperCase() || 'UNKNOWN',
        bg: 'bg-gray-800/40',
        text: 'text-gray-400',
        border: 'border-gray-700/60',
        dot: 'bg-gray-500',
        cardBorder: 'border-l-gray-600',
      }
  }
}

export function statusConfig(status) {
  switch (status?.toLowerCase()) {
    case 'resolved':
      return {
        label: 'RESOLVED',
        bg: 'bg-green-900/30',
        text: 'text-green-400',
        border: 'border-green-800/50',
      }
    case 'in progress':
      return {
        label: 'IN PROGRESS',
        bg: 'bg-blue-900/30',
        text: 'text-blue-400',
        border: 'border-blue-800/50',
      }
    default:
      return {
        label: status?.toUpperCase() || 'UNKNOWN',
        bg: 'bg-gray-800/30',
        text: 'text-gray-400',
        border: 'border-gray-700/50',
      }
  }
}

export function formatTimestamp(ts) {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ts
  }
}
