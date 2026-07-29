import type { CompareResponse } from '../types'

export default function WinnerBanner({ result }: { result: CompareResponse }) {
  const winnerLabel =
    result.winner === 'tie'
      ? 'Tie'
      : result.winner === 'model_a'
        ? `${result.model_a.model} wins`
        : `${result.model_b.model} wins`

  const winnerColor =
    result.winner === 'tie' ? 'text-accent-orange' : 'text-accent-green'

  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-6 py-4">
      <div>
        <div className="font-mono-ui text-xs text-muted">Winner</div>
        <div className={`text-2xl font-bold ${winnerColor}`}>{winnerLabel}</div>
      </div>
      <div className="font-mono-ui text-xs text-muted">Run {result.run_id.slice(0, 8)}</div>
    </div>
  )
}
