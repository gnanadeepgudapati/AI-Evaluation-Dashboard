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

  const data = metricNames.map((metric) => {
    const row: Record<string, string | number> = {
      metric: JUDGE_METRIC_LABELS[metric] ?? metric,
    }
    for (const r of results) {
      row[r.model] = r.judge_scores[metric]?.score ?? 0
    }
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
              key={r.model}
              name={r.model}
              dataKey={r.model}
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
