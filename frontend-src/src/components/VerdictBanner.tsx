import type { CompareResponse } from '../types'

export default function VerdictBanner({ response }: { response: CompareResponse }) {
  const winner = response.results[0]
  const isTie = response.results.filter((r) => r.rank === 1).length > 1
  const scoreLine = response.results
    .map((r) => (r.aggregate_score === null ? '—' : r.aggregate_score.toFixed(2)))
    .join(' vs ')

  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-6 py-4">
      <div>
        <div className="font-mono-ui text-xs text-muted">{isTie ? 'Result' : 'Winner'}</div>
        <div className={`text-2xl font-bold ${isTie ? 'text-accent-orange' : 'text-accent-green'}`}>
          {isTie ? 'Tie' : `${winner.model} wins`}
        </div>
        <div className="font-mono-ui text-xs text-muted">{scoreLine}</div>
      </div>
      <div className="font-mono-ui text-xs text-muted">Run {response.run_id.slice(0, 8)}</div>
    </div>
  )
}
