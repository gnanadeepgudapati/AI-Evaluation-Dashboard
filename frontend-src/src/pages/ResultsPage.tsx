import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useArena } from '../context/ArenaContext'
import { getRun } from '../lib/api'
import ModelCard from '../components/ModelCard'
import RadarMetrics from '../components/RadarMetrics'
import CostLatencyCharts from '../components/CostLatencyCharts'
import WinnerBanner from '../components/WinnerBanner'
import type { CompareResponse } from '../types'

export default function ResultsPage() {
  const { runId } = useParams<{ runId?: string }>()
  const { lastResult, hasAnyKey } = useArena()

  const [result, setResult] = useState<CompareResponse | null>(null)
  const [isDemo, setIsDemo] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    setError(null)
    setIsDemo(false)

    if (runId) {
      setLoading(true)
      getRun(runId)
        .then(setResult)
        .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load run.'))
        .finally(() => setLoading(false))
      return
    }

    if (lastResult) {
      setResult(lastResult)
      return
    }

    // No specific run requested and nothing just run in this session — fall
    // back to demo mode so the page is never empty on first load.
    setLoading(true)
    fetch(`${import.meta.env.BASE_URL}demo/demo_results.json`)
      .then((res) => res.json())
      .then((data: CompareResponse) => {
        setResult(data)
        setIsDemo(true)
      })
      .catch(() => setError('No results to show yet — run a comparison first.'))
      .finally(() => setLoading(false))
  }, [runId, lastResult])

  if (loading) {
    return <div className="font-mono-ui text-sm text-muted">Loading…</div>
  }

  if (error) {
    return (
      <div className="rounded-md border border-accent-red/30 bg-accent-red/10 p-4 text-sm text-accent-red">
        {error}
      </div>
    )
  }

  if (!result) return null

  return (
    <div className="flex flex-col gap-6">
      {isDemo && (
        <div className="rounded-md border border-accent-purple/30 bg-accent-purple/10 px-4 py-3 text-sm text-accent-purple">
          Demo Mode — showing a pre-recorded comparison. Enter your API keys on the Compare page to run a
          live comparison.
        </div>
      )}
      {!isDemo && !hasAnyKey && (
        <div className="rounded-md border border-accent-orange/30 bg-accent-orange/10 px-4 py-3 text-sm text-accent-orange">
          Enter your API keys to run live comparisons.
        </div>
      )}

      <WinnerBanner result={result} />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <ModelCard label="Model A" result={result.model_a} />
        <ModelCard label="Model B" result={result.model_b} />
      </div>

      <RadarMetrics modelA={result.model_a} modelB={result.model_b} />
      <CostLatencyCharts modelA={result.model_a} modelB={result.model_b} />
    </div>
  )
}
