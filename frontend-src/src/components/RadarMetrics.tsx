import {
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts'
import type { ModelResult } from '../types'
import { JUDGE_METRIC_LABELS, MODEL_SERIES_COLORS } from '../types'

export default function RadarMetrics({ results }: { results: ModelResult[] }) {
  const metricNames = Array.from(
    new Set(results.flatMap((r) => Object.keys(r.judge_scores))),
  )

  if (metricNames.length === 0) return null

  // Duplicate models are legal (the same model can be submitted twice in one
  // run). If two results share `r.model`, keying both the chart-data row and
  // the <Radar> dataKey by the bare model name collides: one result's scores
  // silently overwrite the other's in `data`, and both <Radar> series read
  // from the same (last-write-wins) key, so one model's line vanishes rather
  // than just showing a React key warning. Index-qualify series names only
  // when a model name actually repeats, so the common case keeps clean
  // labels.
  const nameCounts = new Map<string, number>()
  for (const r of results) {
    nameCounts.set(r.model, (nameCounts.get(r.model) ?? 0) + 1)
  }
  const seriesNames = results.map((r, i) =>
    (nameCounts.get(r.model) ?? 0) > 1 ? `${r.model} (#${i + 1})` : r.model,
  )

  const data = metricNames.map((metric) => {
    const row: Record<string, string | number> = {
      metric: JUDGE_METRIC_LABELS[metric] ?? metric,
    }
    results.forEach((r, i) => {
      row[seriesNames[i]] = r.judge_scores[metric]?.score ?? 0
    })
    return row
  })

  return (
    <div className="h-80 w-full rounded-lg border border-border bg-surface p-4">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="70%">
          <PolarGrid stroke="#1a2332" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: '#9ca3af', fontSize: 12 }} />
          {results.map((r, i) => (
            <Radar
              key={`${r.model}-${i}`}
              name={seriesNames[i]}
              dataKey={seriesNames[i]}
              stroke={MODEL_SERIES_COLORS[i % 4]}
              fill={MODEL_SERIES_COLORS[i % 4]}
              fillOpacity={0.3}
            />
          ))}
          <Legend />
          <Tooltip contentStyle={{ background: '#0d1219', border: '1px solid #1a2332' }} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
