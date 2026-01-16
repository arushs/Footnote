import { cn } from '../../lib/utils'

interface AgentModeToggleProps {
  enabled: boolean
  onChange: (enabled: boolean) => void
  disabled?: boolean
}

export function AgentModeToggle({ enabled, onChange, disabled = false }: AgentModeToggleProps) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <button
        onClick={() => !disabled && onChange(!enabled)}
        disabled={disabled}
        className={cn(
          'relative inline-flex h-5 w-9 items-center rounded-full transition-colors',
          enabled ? 'bg-blue-600' : 'bg-muted',
          disabled && 'opacity-50 cursor-not-allowed'
        )}
        role="switch"
        aria-checked={enabled}
        aria-label="Enable agent mode"
      >
        <span
          className={cn(
            'inline-block h-3 w-3 transform rounded-full bg-white transition-transform',
            enabled ? 'translate-x-5' : 'translate-x-1'
          )}
        />
      </button>
      <span className={cn(
        enabled ? 'text-blue-600 font-medium' : 'text-muted-foreground',
        disabled && 'opacity-50'
      )}>
        {enabled ? 'Agent Mode' : 'Standard'}
      </span>
      {enabled && (
        <span
          className="text-xs text-muted-foreground"
          title="Multi-turn search with query refinement"
        >
          (slower, more thorough)
        </span>
      )}
    </div>
  )
}
