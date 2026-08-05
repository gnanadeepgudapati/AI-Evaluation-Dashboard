import type { ProgressState } from '../hooks/useEventSource'

export default function ProgressBar({
  state,
  totalModels,
}: {
  state: ProgressState
  totalModels: number
}) {
  // started (1) + one segment per model + judged (1) + complete (1)
  const totalSegments = totalModels + 3
  const filled =
    state.stage === 'idle'
      ? 0
      : state.stage === 'started'
        ? 1
        : state.stage === 'running'
          ? 1 + state.modelsDone
          : state.stage === 'judge_done'
            ? totalSegments - 1
            : totalSegments

  const label =
    state.stage === 'idle'
      ? 'Waiting to start…'
      : state.stage === 'started'
        ? 'Started'
        : state.stage === 'running'
          ? `Models responded: ${state.modelsDone}/${totalModels}`
          : state.stage === 'judge_done'
            ? 'Judged'
            : 'Complete'

  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-2 overflow-hidden rounded-full bg-surface">
        {Array.from({ length: totalSegments }, (_, i) => (
          <div
            key={i}
            className={`flex-1 border-r border-bg last:border-r-0 transition-colors ${
              i < filled ? 'bg-accent-blue' : 'bg-surface'
            }`}
          />
        ))}
      </div>
      <div className="font-mono-ui text-xs text-muted">{label}</div>
    </div>
  )
}
