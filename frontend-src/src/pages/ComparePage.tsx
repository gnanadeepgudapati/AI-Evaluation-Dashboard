import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useArena } from '../context/ArenaContext'
import { useEventSource } from '../hooks/useEventSource'
import { getSuites, postCompare } from '../lib/api'
import ProgressBar from '../components/ProgressBar'
import type { ApiKeys, CompareRequest, ModelSpec, Provider, SuiteMetadata } from '../types'
import { MODELS_BY_PROVIDER } from '../types'

const PROVIDERS: Provider[] = ['anthropic', 'openai', 'gemini']

function ModelPicker({
  label,
  provider,
  model,
  onProviderChange,
  onModelChange,
  onRemove,
}: {
  label: string
  provider: Provider
  model: string
  onProviderChange: (p: Provider) => void
  onModelChange: (m: string) => void
  onRemove?: () => void
}) {
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between">
        <div className="font-mono-ui text-xs text-muted uppercase">{label}</div>
        {onRemove && (
          <button type="button" onClick={onRemove} className="font-mono-ui text-xs text-accent-red">
            remove
          </button>
        )}
      </div>
      <select
        className="rounded-md border border-border bg-bg px-3 py-2 text-sm"
        value={provider}
        onChange={(e) => onProviderChange(e.target.value as Provider)}
      >
        {PROVIDERS.map((p) => (
          <option key={p} value={p}>
            {p}
          </option>
        ))}
      </select>
      <select
        className="rounded-md border border-border bg-bg px-3 py-2 text-sm"
        value={model}
        onChange={(e) => onModelChange(e.target.value)}
      >
        {MODELS_BY_PROVIDER[provider].map((m) => (
          <option key={m} value={m}>
            {m}
          </option>
        ))}
      </select>
    </div>
  )
}

export default function ComparePage() {
  const { apiKeys, setApiKeys, setLastResult } = useArena()
  const navigate = useNavigate()

  const [lineup, setLineup] = useState<ModelSpec[]>([
    { provider: 'anthropic', model: MODELS_BY_PROVIDER.anthropic[0] },
    { provider: 'openai', model: MODELS_BY_PROVIDER.openai[0] },
  ])

  function updateLineup(index: number, spec: ModelSpec) {
    setLineup(lineup.map((existing, i) => (i === index ? spec : existing)))
  }

  function addModel() {
    if (lineup.length >= 4) return
    setLineup([...lineup, { provider: 'gemini', model: MODELS_BY_PROVIDER.gemini[0] }])
  }

  function removeModel(index: number) {
    if (lineup.length <= 2) return
    setLineup(lineup.filter((_, i) => i !== index))
  }

  const activeProviders = useMemo(
    () => Array.from(new Set(lineup.map((spec) => spec.provider))),
    [lineup],
  )

  const [mode, setMode] = useState<'prompt' | 'suite'>('prompt')
  const [prompt, setPrompt] = useState('')
  const [suites, setSuites] = useState<SuiteMetadata[]>([])
  const [suiteId, setSuiteId] = useState('')
  const [consistencyRuns, setConsistencyRuns] = useState(1)

  const [runId, setRunId] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const progress = useEventSource(runId)

  useEffect(() => {
    getSuites()
      .then((data) => {
        setSuites(data)
        if (data.length > 0) setSuiteId(data[0].id)
      })
      .catch(() => setSuites([]))
  }, [])

  function updateKey(provider: keyof ApiKeys, value: string) {
    setApiKeys({ ...apiKeys, [provider]: value })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)

    const newRunId = crypto.randomUUID()
    setRunId(newRunId)

    const request: CompareRequest = {
      models: lineup,
      consistency_runs: consistencyRuns,
      run_id: newRunId,
      ...(mode === 'prompt' ? { prompt } : { suite_id: suiteId }),
    }

    try {
      const result = await postCompare(request, apiKeys)
      setLastResult(result)
      navigate('/results')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Comparison failed.')
    } finally {
      setSubmitting(false)
      setRunId(null)
    }
  }

  const canSubmit = mode === 'prompt' ? prompt.trim().length > 0 : suiteId.length > 0

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold">Compare models</h1>
        <p className="mt-1 text-sm text-muted">
          Bring your own API keys — they are sent as request headers and never stored.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {lineup.map((spec, index) => (
          <ModelPicker
            key={index}
            label={`Model ${index + 1}`}
            provider={spec.provider}
            model={spec.model}
            onProviderChange={(p) => updateLineup(index, { provider: p, model: MODELS_BY_PROVIDER[p][0] })}
            onModelChange={(m) => updateLineup(index, { ...spec, model: m })}
            onRemove={lineup.length > 2 ? () => removeModel(index) : undefined}
          />
        ))}
        {lineup.length < 4 && (
          <button
            type="button"
            onClick={addModel}
            className="flex min-h-32 items-center justify-center rounded-lg border border-dashed border-border text-sm text-muted hover:text-text"
          >
            + Add model ({lineup.length}/4)
          </button>
        )}
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {activeProviders.map((p) => (
          <div key={p} className="flex flex-col gap-1">
            <label className="font-mono-ui text-xs text-muted uppercase">{p} API key</label>
            <input
              type="password"
              autoComplete="off"
              placeholder={`Your ${p} key`}
              className="rounded-md border border-border bg-surface px-3 py-2 text-sm"
              value={apiKeys[p]}
              onChange={(e) => updateKey(p, e.target.value)}
            />
          </div>
        ))}
      </div>

      <div className="flex gap-2">
        <button
          type="button"
          className={`rounded-md px-4 py-2 text-sm font-mono-ui ${mode === 'prompt' ? 'bg-accent-blue/20 text-accent-blue' : 'bg-surface text-muted'}`}
          onClick={() => setMode('prompt')}
        >
          Custom Prompt
        </button>
        <button
          type="button"
          className={`rounded-md px-4 py-2 text-sm font-mono-ui ${mode === 'suite' ? 'bg-accent-blue/20 text-accent-blue' : 'bg-surface text-muted'}`}
          onClick={() => setMode('suite')}
        >
          Run Suite
        </button>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {mode === 'prompt' ? (
          <textarea
            className="min-h-32 rounded-md border border-border bg-surface p-3 text-sm"
            placeholder="Enter a prompt to send to both models…"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
          />
        ) : (
          <select
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm"
            value={suiteId}
            onChange={(e) => setSuiteId(e.target.value)}
          >
            {suites.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name} ({s.item_count} items)
              </option>
            ))}
          </select>
        )}

        <div className="flex items-center gap-3">
          <label className="font-mono-ui text-xs text-muted">Consistency runs</label>
          <select
            className="rounded-md border border-border bg-surface px-3 py-2 text-sm"
            value={consistencyRuns}
            onChange={(e) => setConsistencyRuns(Number(e.target.value))}
          >
            <option value={1}>1 (default)</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </div>

        {runId && <ProgressBar state={progress} totalModels={lineup.length} />}
        {error && (
          <div className="rounded-md border border-accent-red/30 bg-accent-red/10 p-3 text-sm text-accent-red">
            {error}
          </div>
        )}

        <button
          type="submit"
          disabled={!canSubmit || submitting}
          className="w-fit rounded-md bg-accent-blue px-6 py-2 font-semibold text-bg disabled:opacity-40"
        >
          {submitting ? 'Running…' : 'Run Comparison'}
        </button>
      </form>
    </div>
  )
}
