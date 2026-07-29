// Shared TypeScript types mirroring the FastAPI Pydantic contracts in
// api/models.py. Keep these in sync with the backend by hand — no codegen.

export type Provider = 'anthropic' | 'openai' | 'gemini'

export interface JudgeScore {
  score: number
  reasoning: string
}

export interface ModelResult {
  model: string
  provider: Provider
  response_text: string
  input_tokens: number
  output_tokens: number
  latency_ms: number
  cost_usd: number
  judge_scores: Record<string, JudgeScore>
  code_pass_rate: number | null
  consistency: number | null
  error: string | null
}

export type Winner = 'model_a' | 'model_b' | 'tie'

export interface CompareResponse {
  run_id: string
  model_a: ModelResult
  model_b: ModelResult
  winner: Winner
  created_at: string
}

export interface CompareRequest {
  model_a: string
  model_b: string
  provider_a: Provider
  provider_b: Provider
  prompt?: string
  suite_id?: string
  consistency_runs?: number
  run_id?: string
}

export interface RunSummary {
  run_id: string
  model_a: string
  model_b: string
  winner: Winner | null
  created_at: string
}

export interface RunsListResponse {
  runs: RunSummary[]
  total: number
}

export interface SuiteMetadata {
  id: string
  name: string
  item_count: number
}

export interface ApiKeys {
  anthropic: string
  openai: string
  gemini: string
}

export const MODELS_BY_PROVIDER: Record<Provider, string[]> = {
  anthropic: ['claude-3-5-haiku-20241022', 'claude-3-5-sonnet-20241022', 'claude-3-opus-20240229'],
  openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo'],
  gemini: ['gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-2.0-flash'],
}

export const JUDGE_METRIC_LABELS: Record<string, string> = {
  groundedness: 'Groundedness',
  correctness: 'Correctness',
  relevance: 'Relevance',
  safety: 'Safety',
  completeness: 'Completeness',
}
