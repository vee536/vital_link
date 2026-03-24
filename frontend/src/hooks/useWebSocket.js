import { useEffect, useRef, useCallback, useReducer } from 'react'
import { RECONNECT_DELAY_MS, MAX_RECONNECT_ATTEMPTS } from '../utils/config'

// ── State ────────────────────────────────────────────────────────────────────

const initialState = {
  // ambulances is a map: { [ambulance_id]: latestVitalsObject }
  ambulances: {},
  status: 'connecting', // 'connecting' | 'connected' | 'disconnected' | 'reconnecting'
  lastMessage: null,
  reconnectCount: 0,
}

// ── Reducer ───────────────────────────────────────────────────────────────────
// MESSAGE upserts the latest payload keyed by ambulance_id.
// If ambulance_id is missing, falls back to 'UNKNOWN' so old payloads still render.

function reducer(state, action) {
  switch (action.type) {
    case 'SET_STATUS':
      return { ...state, status: action.payload }

    case 'SET_RECONNECT_COUNT':
      return { ...state, reconnectCount: action.payload }

    case 'MESSAGE': {
      const data = action.payload
      const id = data.ambulance_id || 'UNKNOWN'
      return {
        ...state,
        lastMessage: data,
        ambulances: {
          ...state.ambulances,
          [id]: data,   // ✅ upsert: create or overwrite this ambulance's entry
        },
      }
    }

    default:
      return state
  }
}

// ── Hook ─────────────────────────────────────────────────────────────────────

export function useWebSocket() {
  const [state, dispatch] = useReducer(reducer, initialState)
  const wsRef = useRef(null)
  const reconnectTimerRef = useRef(null)
  const reconnectCountRef = useRef(0)
  const unmountedRef = useRef(false)

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

  const connect = useCallback(() => {
    if (unmountedRef.current) return

    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
    }

    const ws = new WebSocket("wss://018nlv643l.execute-api.eu-north-1.amazonaws.com/production")
    wsRef.current = ws

    ws.onopen = () => {
      if (unmountedRef.current) return
      reconnectCountRef.current = 0
      dispatch({ type: 'SET_STATUS', payload: 'connected' })
      dispatch({ type: 'SET_RECONNECT_COUNT', payload: 0 })
    }

    ws.onmessage = (event) => {
      if (unmountedRef.current) return
      try {
        const data = JSON.parse(event.data)
        console.log('[VitalLink] Vitals update:', data)
        dispatch({ type: 'MESSAGE', payload: data })
      } catch (err) {
        console.warn('[VitalLink] Failed to parse WebSocket message:', err)
      }
    }

    ws.onerror = () => {
      // always followed by onclose — reconnect logic lives there
    }

    ws.onclose = () => {
      if (unmountedRef.current) return

      reconnectCountRef.current += 1

      if (reconnectCountRef.current >= MAX_RECONNECT_ATTEMPTS) {
        dispatch({ type: 'SET_STATUS', payload: 'disconnected' })
        return
      }

      dispatch({ type: 'SET_STATUS', payload: 'reconnecting' })
      dispatch({ type: 'SET_RECONNECT_COUNT', payload: reconnectCountRef.current })

      clearReconnectTimer()
      reconnectTimerRef.current = setTimeout(() => {
        if (!unmountedRef.current) connect()
      }, RECONNECT_DELAY_MS)
    }
  }, [clearReconnectTimer])

  useEffect(() => {
    unmountedRef.current = false
    connect()

    return () => {
      unmountedRef.current = true
      clearReconnectTimer()
      if (wsRef.current) {
        wsRef.current.onclose = null
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [connect, clearReconnectTimer])

  return {
    ambulances: state.ambulances,           // ✅ map of all live ambulances
    ambulanceCount: Object.keys(state.ambulances).length,
    // backwards-compat: latest message regardless of source
    latestVitals: state.lastMessage,
    status: state.status,
    lastMessage: state.lastMessage,
    reconnectCount: state.reconnectCount,
  }
}
