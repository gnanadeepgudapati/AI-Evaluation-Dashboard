interface ProgressBarProps {
  stage: 'idle' | 'started' | 'model_a_done' | 'model_b_done' | 'judge_done' | 'complete'
}

const STAGES: { key: ProgressBarProps['stage']; label: string }[] = [
  { key: 'started', label: 'Started' },
  { key: 'model_a_done', label: 'Model A responded' },
  { key: 'model_b_done', label: 'Model B responded' },
  { key: 'judge_done', label: 'Judged' },
  { key: 'complete', label: 'Complete' },
]

export default function ProgressBar({ stage }: ProgressBarProps) {
  const currentIndex = STAGES.findIndex((s) => s.key === stage)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex h-2 overflow-hidden rounded-full bg-surface">
        {STAGES.map((s, i) => (
          <div
            key={s.key}
            className={`flex-1 border-r border-bg last:border-r-0 transition-colors ${
              i <= currentIndex ? 'bg-accent-blue' : 'bg-surface'
            }`}
          />
        ))}
      </div>
      <div className="font-mono-ui text-xs text-muted">
        {currentIndex >= 0 ? STAGES[currentIndex].label : 'Waiting to start…'}
      </div>
    </div>
  )
}
