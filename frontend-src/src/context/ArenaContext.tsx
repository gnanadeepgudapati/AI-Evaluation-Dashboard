// Session-scoped state: BYOK API keys (never persisted to storage) and the
// most recent comparison result (so Results can render right after a run
// without needing a round-trip through /runs/{id}).

import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'
import type { ApiKeys, CompareResponse } from '../types'

interface ArenaContextValue {
  apiKeys: ApiKeys
  setApiKeys: (keys: ApiKeys) => void
  hasAnyKey: boolean
  lastResult: CompareResponse | null
  setLastResult: (result: CompareResponse | null) => void
}

const EMPTY_KEYS: ApiKeys = { anthropic: '', openai: '', gemini: '' }

const ArenaContext = createContext<ArenaContextValue | null>(null)

export function ArenaProvider({ children }: { children: ReactNode }) {
  const [apiKeys, setApiKeys] = useState<ApiKeys>(EMPTY_KEYS)
  const [lastResult, setLastResult] = useState<CompareResponse | null>(null)

  const hasAnyKey = useMemo(
    () => Object.values(apiKeys).some((value) => value.trim().length > 0),
    [apiKeys],
  )

  const value = useMemo(
    () => ({ apiKeys, setApiKeys, hasAnyKey, lastResult, setLastResult }),
    [apiKeys, hasAnyKey, lastResult],
  )

  return <ArenaContext.Provider value={value}>{children}</ArenaContext.Provider>
}

export function useArena(): ArenaContextValue {
  const ctx = useContext(ArenaContext)
  if (!ctx) throw new Error('useArena must be used within ArenaProvider')
  return ctx
}
