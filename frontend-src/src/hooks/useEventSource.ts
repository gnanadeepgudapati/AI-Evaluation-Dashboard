// Wraps the native EventSource API for /stream/{run_id}. Because POST
// /compare is a single request/response (not fire-and-forget), the caller
// must open this stream with a client-generated run_id *before* posting the
// compare request, passing the same run_id in the request body so the
// server publishes to a queue this stream is already subscribed to.

import { useEffect, useRef, useState } from 'react'

export type ProgressStage = 'idle' | 'started' | 'model_a_done' | 'model_b_done' | 'judge_done' | 'complete'

interface StreamEvent {
  event: string
  run_id: string
  latency_ms?: number
}

export function useEventSource(runId: string | null) {
  const [stage, setStage] = useState<ProgressStage>('idle')
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!runId) return

    setStage('idle')
    const source = new EventSource(`/stream/${runId}`)
    sourceRef.current = source

    const stages: ProgressStage[] = ['started', 'model_a_done', 'model_b_done', 'judge_done', 'complete']
    for (const stageName of stages) {
      source.addEventListener(stageName, (evt: MessageEvent) => {
        try {
          const data = JSON.parse(evt.data) as StreamEvent
          setStage(data.event as ProgressStage)
        } catch {
          setStage(stageName)
        }
        if (stageName === 'complete') {
          source.close()
        }
      })
    }

    source.onerror = () => {
      // Connection closed by server (timeout or complete) — nothing to do.
    }

    return () => {
      source.close()
      sourceRef.current = null
    }
  }, [runId])

  return stage
}
