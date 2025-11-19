import { useEffect, useRef, useState } from 'react'

export interface EventSourceOptions {
  onMessage?: (event: MessageEvent) => void
  onError?: (event: Event) => void
  onOpen?: (event: Event) => void
}

/**
 * EventSource Hook
 * 用于订阅 Server-Sent Events (SSE)
 */
export function useEventSource(url: string | null, options: EventSourceOptions = {}) {
  const [status, setStatus] = useState<'connecting' | 'open' | 'closed' | 'error'>(
    'connecting'
  )
  const eventSourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!url) {
      setStatus('closed')
      return
    }

    const eventSource = new EventSource(url)
    eventSourceRef.current = eventSource

    eventSource.onopen = (event) => {
      setStatus('open')
      options.onOpen?.(event)
    }

    eventSource.onerror = (event) => {
      setStatus('error')
      options.onError?.(event)
    }

    eventSource.onmessage = (event) => {
      options.onMessage?.(event)
    }

    return () => {
      eventSource.close()
      eventSourceRef.current = null
      setStatus('closed')
    }
  }, [url])

  const close = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
      setStatus('closed')
    }
  }

  return { status, close }
}

