import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { ModelResult } from '../types'

export default function CostLatencyCharts({ results }: { results: ModelResult[] }) {
  const costData = results.map((r) => ({ name: r.model, cost: r.cost_usd }))
  const latencyData = results.map((r) => ({ name: r.model, latency: r.latency_ms }))

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div className="h-64 rounded-lg border border-border bg-surface p-4">
        <div className="mb-2 font-mono-ui text-xs text-muted">Cost (USD)</div>
        <ResponsiveContainer width="100%" height="85%">
          <BarChart data={costData}>
            <CartesianGrid stroke="#1a2332" strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
            <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
            <Tooltip contentStyle={{ background: '#0d1219', border: '1px solid #1a2332' }} />
            <Legend />
            <Bar dataKey="cost" fill="#fb923c" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="h-64 rounded-lg border border-border bg-surface p-4">
        <div className="mb-2 font-mono-ui text-xs text-muted">Latency (ms, p50)</div>
        <ResponsiveContainer width="100%" height="85%">
          <BarChart data={latencyData}>
            <CartesianGrid stroke="#1a2332" strokeDasharray="3 3" />
            <XAxis dataKey="name" tick={{ fill: '#9ca3af', fontSize: 11 }} />
            <YAxis tick={{ fill: '#9ca3af', fontSize: 11 }} />
            <Tooltip contentStyle={{ background: '#0d1219', border: '1px solid #1a2332' }} />
            <Legend />
            <Bar dataKey="latency" fill="#ff7a1a" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
