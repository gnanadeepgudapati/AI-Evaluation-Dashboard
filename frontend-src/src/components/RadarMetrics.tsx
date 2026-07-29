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
import { JUDGE_METRIC_LABELS } from '../types'

export default function RadarMetrics({ modelA, modelB }: { modelA: ModelResult; modelB: ModelResult }) {
  const metricNames = Array.from(
    new Set([...Object.keys(modelA.judge_scores), ...Object.keys(modelB.judge_scores)]),
  )

  if (metricNames.length === 0) return null

  const data = metricNames.map((metric) => ({
    metric: JUDGE_METRIC_LABELS[metric] ?? metric,
    'Model A': modelA.judge_scores[metric]?.score ?? 0,
    'Model B': modelB.judge_scores[metric]?.score ?? 0,
  }))

  return (
    <div className="h-80 w-full rounded-lg border border-border bg-surface p-4">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="70%">
          <PolarGrid stroke="#1a2332" />
          <PolarAngleAxis dataKey="metric" tick={{ fill: '#9ca3af', fontSize: 12 }} />
          <Radar name="Model A" dataKey="Model A" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.3} />
          <Radar name="Model B" dataKey="Model B" stroke="#a78bfa" fill="#a78bfa" fillOpacity={0.3} />
          <Legend />
          <Tooltip contentStyle={{ background: '#0d1219', border: '1px solid #1a2332' }} />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}
