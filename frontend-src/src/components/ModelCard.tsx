import type { ModelResult } from '../types'
import { JUDGE_METRIC_LABELS } from '../types'

function formatUsd(value: number): string {
  return `$${value.toFixed(4)}`
}

export default function ModelCard({ label, result }: { label: string; result: ModelResult }) {
  return (
    <div className="flex flex-col gap-4 rounded-lg border border-border bg-surface p-5">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-mono-ui text-xs text-muted uppercase">{label}</div>
          <div className="text-lg font-semibold">{result.model}</div>
          <div className="font-mono-ui text-xs text-accent-purple">{result.provider}</div>
        </div>
        {result.error ? (
          <span className="rounded-full bg-accent-red/15 px-3 py-1 font-mono-ui text-xs text-accent-red">
            error
          </span>
        ) : (
          <span className="rounded-full bg-accent-green/15 px-3 py-1 font-mono-ui text-xs text-accent-green">
            ok
          </span>
        )}
      </div>

      {result.error ? (
        <div className="rounded-md border border-accent-red/30 bg-accent-red/10 p-3 font-mono-ui text-sm text-accent-red">
          {result.error}
        </div>
      ) : (
        <div className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-md bg-bg p-3 font-mono-ui text-sm text-text">
          {result.response_text || '(empty response)'}
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 font-mono-ui text-xs">
        <div className="rounded-md bg-bg p-2">
          <div className="text-muted">Latency (p50)</div>
          <div className="text-accent-blue">{result.latency_ms.toFixed(0)} ms</div>
        </div>
        <div className="rounded-md bg-bg p-2">
          <div className="text-muted">Cost</div>
          <div className="text-accent-orange">{formatUsd(result.cost_usd)}</div>
        </div>
        <div className="rounded-md bg-bg p-2">
          <div className="text-muted">Tokens (in/out)</div>
          <div>
            {result.input_tokens} / {result.output_tokens}
          </div>
        </div>
        {result.consistency !== null && (
          <div className="rounded-md bg-bg p-2">
            <div className="text-muted">Consistency</div>
            <div className="text-accent-purple">{(result.consistency * 100).toFixed(0)}%</div>
          </div>
        )}
        {result.code_pass_rate !== null && (
          <div className="rounded-md bg-bg p-2">
            <div className="text-muted">Code pass rate</div>
            <div className="text-accent-green">{(result.code_pass_rate * 100).toFixed(0)}%</div>
          </div>
        )}
      </div>

      {Object.keys(result.judge_scores).length > 0 && (
        <div className="flex flex-col gap-1">
          {Object.entries(result.judge_scores).map(([metric, judge]) => (
            <div key={metric} className="flex items-center justify-between font-mono-ui text-xs">
              <span className="text-muted">{JUDGE_METRIC_LABELS[metric] ?? metric}</span>
              <span className="text-accent-blue">{judge.score.toFixed(2)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
