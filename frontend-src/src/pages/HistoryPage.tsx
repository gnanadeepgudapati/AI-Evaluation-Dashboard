import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getRuns } from '../lib/api'
import type { RunSummary } from '../types'

const PAGE_SIZE = 20

export default function HistoryPage() {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [total, setTotal] = useState(0)
  const [offset, setOffset] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    getRuns(PAGE_SIZE, offset)
      .then((data) => {
        setRuns(data.runs)
        setTotal(data.total)
      })
      .catch((err) => setError(err instanceof Error ? err.message : 'Failed to load history.'))
  }, [offset])

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-3xl font-bold">Run History</h1>

      {error && (
        <div className="rounded-md border border-accent-red/30 bg-accent-red/10 p-4 text-sm text-accent-red">
          {error}
        </div>
      )}

      <div className="overflow-hidden rounded-lg border border-border">
        <table className="w-full text-left text-sm">
          <thead className="bg-surface font-mono-ui text-xs text-muted uppercase">
            <tr>
              <th className="px-4 py-3">Date</th>
              <th className="px-4 py-3">Models</th>
              <th className="px-4 py-3">Winner</th>
              <th className="px-4 py-3">Report</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr
                key={run.run_id}
                className="cursor-pointer border-t border-border hover:bg-surface"
                onClick={() => navigate(`/results/${run.run_id}`)}
              >
                <td className="px-4 py-3 font-mono-ui text-xs text-muted">
                  {new Date(run.created_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 font-mono-ui">{run.models.join(' vs ')}</td>
                <td className="px-4 py-3">
                  <span
                    className={run.winner === 'tie' ? 'text-accent-orange' : 'text-accent-green'}
                  >
                    {run.winner === 'tie' ? 'Tie' : (run.winner ?? 'unknown')}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    className="font-mono-ui text-xs text-accent-blue"
                    onClick={(e) => {
                      e.stopPropagation()
                      navigate(`/report/${run.run_id}`)
                    }}
                  >
                    Open report →
                  </button>
                </td>
              </tr>
            ))}
            {runs.length === 0 && !error && (
              <tr>
                <td colSpan={4} className="px-4 py-6 text-center text-muted">
                  No runs yet — comparisons you run will show up here.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between font-mono-ui text-xs text-muted">
        <button
          type="button"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          className="rounded-md bg-surface px-3 py-1 disabled:opacity-30"
        >
          Previous
        </button>
        <span>
          {offset + 1}–{offset + runs.length} of {total}
        </span>
        <button
          type="button"
          disabled={offset + PAGE_SIZE >= total}
          onClick={() => setOffset(offset + PAGE_SIZE)}
          className="rounded-md bg-surface px-3 py-1 disabled:opacity-30"
        >
          Next
        </button>
      </div>
    </div>
  )
}
