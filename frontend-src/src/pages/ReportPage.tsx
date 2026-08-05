import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { getRun, reportMdUrl } from '../lib/api'
import CostLatencyCharts from '../components/CostLatencyCharts'
import Leaderboard from '../components/Leaderboard'
import RadarMetrics from '../components/RadarMetrics'
import VerdictBanner from '../components/VerdictBanner'
import type { CompareResponse } from '../types'

export default function ReportPage() {
  const { runId } = useParams<{ runId: string }>()
  const [result, setResult] = useState<CompareResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!runId) return
    getRun(runId)
      .then(setResult)
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load run.'))
  }, [runId])

  if (error) {
    return (
      <div className="rounded-md border border-accent-red/30 bg-accent-red/10 p-4 text-sm text-accent-red">
        {error}
      </div>
    )
  }
  if (!result) return <div className="font-mono-ui text-sm text-muted">Loading report…</div>

  return (
    <div className="print-report flex flex-col gap-6">
      <div className="no-print flex items-center justify-between">
        <h1 className="text-3xl font-bold">Comparison Report</h1>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => window.print()}
            className="rounded-md bg-surface px-4 py-2 text-sm font-mono-ui"
          >
            Print / Save PDF
          </button>
          <a
            href={reportMdUrl(result.run_id)}
            className="rounded-md bg-accent-blue px-4 py-2 text-sm font-semibold text-bg"
          >
            Download .md
          </a>
        </div>
      </div>

      <div className="font-mono-ui text-xs text-muted">
        Run {result.run_id} · {new Date(result.created_at).toLocaleString()} ·{' '}
        {result.results.length} models
      </div>

      <VerdictBanner response={result} />
      <Leaderboard results={result.results} />
      <RadarMetrics results={result.results} />
      <CostLatencyCharts results={result.results} />

      <div className="flex flex-col gap-4">
        <h2 className="text-xl font-bold">Responses</h2>
        {result.results.map((r, i) => (
          <details key={`${r.model}-${i}`} className="rounded-lg border border-border bg-surface p-4" open>
            <summary className="cursor-pointer font-semibold">
              #{r.rank} {r.model}{' '}
              <span className="font-mono-ui text-xs text-accent-purple">{r.provider}</span>
            </summary>
            {r.error ? (
              <div className="mt-3 rounded-md border border-accent-red/30 bg-accent-red/10 p-3 font-mono-ui text-sm text-accent-red">
                {r.error}
              </div>
            ) : (
              <pre className="mt-3 max-h-96 overflow-y-auto whitespace-pre-wrap rounded-md bg-bg p-3 font-mono-ui text-sm">
                {r.response_text || '(empty response)'}
              </pre>
            )}
          </details>
        ))}
      </div>
    </div>
  )
}
