// Wraps the native EventSource API for /stream/{run_id}. The caller opens the
// stream with a client-generated run_id BEFORE posting /compare (same run_id
// in the body) so the server publishes to a queue this stream already reads.
//
// Event sequence: started -> N x model_done (payload carries `slot`) ->
// judge_done -> complete.

import { useEffect, useRef, useState } from 'react'
import { streamUrl } from '../lib/api'

export interface ProgressState {
  stage: 'idle' | 'started' | 'running' | 'judge_done' | 'complete'
  modelsDone: number
}

const IDLE: ProgressState = { stage: 'idle', modelsDone: 0 }

export function useEventSource(runId: string | null): ProgressState {
  const [state, setState] = useState<ProgressState>(IDLE)
  const sourceRef = useRef<EventSource | null>(null)

  useEffect(() => {
    if (!runId) return

    setState(IDLE)
    const source = new EventSource(streamUrl(runId))
    sourceRef.current = source

    source.addEventListener('started', () => setState({ stage: 'started', modelsDone: 0 }))
    source.addEventListener('model_done', () =>
      setState((prev) => ({ stage: 'running', modelsDone: prev.modelsDone + 1 })),
    )
    source.addEventListener('judge_done', () =>
      setState((prev) => ({ ...prev, stage: 'judge_done' })),
    )
    source.addEventListener('complete', () => {
      setState((prev) => ({ ...prev, stage: 'complete' }))
      source.close()
    })

    source.onerror = () => {
      // Connection closed by server (timeout or complete) — nothing to do.
    }

    return () => {
      source.close()
      sourceRef.current = null
    }
  }, [runId])

  return state
}
