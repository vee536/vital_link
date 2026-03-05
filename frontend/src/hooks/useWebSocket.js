import { useEffect, useRef, useCallback, useReducer } from 'react'
import { WS_URL, RECONNECT_DELAY_MS, MAX_RECONNECT_ATTEMPTS } from '../utils/config'

// ── State ────────────────────────────────────────────────────────────────────

const initialState = {
  ambulances: [],     // { [ambulance_id]: latestMessage }
  status: 'connecting', // 'connecting' | 'connected' | 'disconnected' | 'reconnecting'
  lastMessage: null,
  reconnectCount: 0,
}

function reducer(state, action) {
  switch (action.type) {
    case 'SET_STATUS':
      return { ...state, status: action.payload }

    case 'SET_RECONNECT_COUNT':
      return { ...state, reconnectCount: action.payload }

    
function reducer(state, action) {
  switch (action.type) {
    case 'SET_STATUS':
      return { ...state, status: action.payload }

    case 'SET_RECONNECT_COUNT':
      return { ...state, reconnectCount: action.payload }

    case 'MESSAGE': {
  const data = action.payload

  return {
    ...state,
    lastMessage: data,
    ambulances: [data],   // store latest message as array
  }
}

    default:
      return state
  }
}

// ── Hook ─────────────────────────────────────────────────────────────────────


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

    // Close existing socket if any
    if (wsRef.current) {
      wsRef.current.onclose = null
      wsRef.current.close()
    }

    const ws = new WebSocket("wss://018nlv643l.execute-api.eu-north-1.amazonaws.com/production");
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
    console.log("Reducer updating with:", data)
    dispatch({ type: 'MESSAGE', payload: data })
  } catch (err) {
    console.warn('[VitalLink] Failed to parse WebSocket message:', err)
  }
}

    ws.onerror = () => {
      // onerror is always followed by onclose, so we handle reconnect there
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
    ambulances: state.ambulances,
    status: state.status,
    lastMessage: state.lastMessage,
    reconnectCount: state.reconnectCount,
  }
}
