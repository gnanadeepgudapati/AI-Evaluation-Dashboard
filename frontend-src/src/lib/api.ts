// Thin fetch wrapper for the arena API. BYOK keys are passed as headers on
// a per-call basis and never persisted anywhere (no localStorage/cookies).
//
// API_BASE defaults to "" (relative paths), which is correct when FastAPI
// serves this build itself (Docker / local dev via the Vite proxy). Set
// VITE_API_BASE_URL at build time if the frontend is deployed separately
// from the backend (e.g. frontend on Vercel, backend on Render).

import type {
  ApiKeys,
  CompareRequest,
  CompareResponse,
  RunsListResponse,
  SuiteMetadata,
} from '../types'

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? ''

const KEY_HEADERS: Record<keyof ApiKeys, string> = {
  anthropic: 'X-Anthropic-Key',
  openai: 'X-OpenAI-Key',
  gemini: 'X-Gemini-Key',
}

function buildKeyHeaders(keys: ApiKeys): HeadersInit {
  const headers: Record<string, string> = {}
  for (const provider of Object.keys(KEY_HEADERS) as (keyof ApiKeys)[]) {
    const value = keys[provider]
    if (value) headers[KEY_HEADERS[provider]] = value
  }
  return headers
}

async function parseOrThrow<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? JSON.stringify(body)
    } catch {
      // ignore — fall back to statusText
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  return res.json() as Promise<T>
}

export async function postCompare(request: CompareRequest, keys: ApiKeys): Promise<CompareResponse> {
  const res = await fetch(`${API_BASE}/compare`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...buildKeyHeaders(keys),
    },
    body: JSON.stringify(request),
  })
  return parseOrThrow<CompareResponse>(res)
}

export async function getSuites(): Promise<SuiteMetadata[]> {
  const res = await fetch(`${API_BASE}/suites`)
  return parseOrThrow<SuiteMetadata[]>(res)
}

export async function getRuns(limit = 50, offset = 0): Promise<RunsListResponse> {
  const res = await fetch(`${API_BASE}/runs?limit=${limit}&offset=${offset}`)
  return parseOrThrow<RunsListResponse>(res)
}

export async function getRun(runId: string): Promise<CompareResponse> {
  const res = await fetch(`${API_BASE}/runs/${runId}`)
  return parseOrThrow<CompareResponse>(res)
}

export function streamUrl(runId: string): string {
  return `${API_BASE}/stream/${runId}`
}

export function reportMdUrl(runId: string): string {
  return `${API_BASE}/runs/${runId}/report.md`
}
