import type { ModelResult } from '../types'

function usd(value: number | null): string {
  return value === null ? '—' : `$${value.toFixed(4)}`
}

function num(value: number | null, digits = 2, suffix = ''): string {
  return value === null ? '—' : `${value.toFixed(digits)}${suffix}`
}

export default function Leaderboard({ results }: { results: ModelResult[] }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-left text-sm">
        <thead className="bg-surface font-mono-ui text-xs text-muted uppercase">
          <tr>
            <th className="px-3 py-3">#</th>
            <th className="px-3 py-3">Model</th>
            <th className="px-3 py-3">Aggregate</th>
            <th className="px-3 py-3">Cost</th>
            <th className="px-3 py-3">Cost/task</th>
            <th className="px-3 py-3">Cost/1k tasks</th>
            <th className="px-3 py-3">p50</th>
            <th className="px-3 py-3">Tok/s</th>
            <th className="px-3 py-3">Consistency</th>
          </tr>
        </thead>
        <tbody>
          {results.map((r, i) => (
            <tr key={`${r.model}-${i}`} className="border-t border-border">
              <td className="px-3 py-3 font-mono-ui">
                {r.rank === 1 && !r.error ? '🏆' : r.rank}
              </td>
              <td className="px-3 py-3">
                <span className="font-mono-ui font-bold">{r.model}</span>{' '}
                <span className="font-mono-ui text-xs text-accent-purple">{r.provider}</span>
                {r.error && (
                  <span className="ml-2 rounded-full bg-accent-red/15 px-2 py-0.5 font-mono-ui text-xs text-accent-red">
                    failed
                  </span>
                )}
              </td>
              <td className="px-3 py-3 text-accent-blue">{num(r.aggregate_score)}</td>
              <td className="px-3 py-3 text-accent-orange">{usd(r.cost_usd)}</td>
              <td className="px-3 py-3">{usd(r.cost_per_task)}</td>
              <td className="px-3 py-3">{usd(r.cost_per_1k_tasks)}</td>
              <td className="px-3 py-3">{num(r.latency_ms, 0, ' ms')}</td>
              <td className="px-3 py-3">{num(r.tokens_per_sec, 1)}</td>
              <td className="px-3 py-3">{num(r.consistency)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
