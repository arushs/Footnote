import { Search, RefreshCw, FileText, Loader2 } from 'lucide-react'
import type { AgentStatus } from '../../types'

interface AgentStatusIndicatorProps {
  status: AgentStatus
}

const phaseConfig = {
  searching: {
    icon: Search,
    label: 'Searching documents',
    color: 'text-blue-500',
  },
  rewriting: {
    icon: RefreshCw,
    label: 'Refining search query',
    color: 'text-amber-500',
  },
  reading_file: {
    icon: FileText,
    label: 'Reading file content',
    color: 'text-green-500',
  },
  processing: {
    icon: Loader2,
    label: 'Processing results',
    color: 'text-purple-500',
  },
  generating: {
    icon: Loader2,
    label: 'Generating response',
    color: 'text-foreground',
  },
}

export function AgentStatusIndicator({ status }: AgentStatusIndicatorProps) {
  const config = phaseConfig[status.phase] || phaseConfig.processing
  const Icon = config.icon

  return (
    <div className="flex items-center gap-3 px-4 py-3 bg-muted/50 border-b border-border">
      <div className={`flex items-center justify-center ${config.color}`}>
        <Icon className="h-4 w-4 animate-pulse" />
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-foreground">
            {config.label}
          </span>
          {status.tool && status.phase !== 'generating' && (
            <span className="text-xs text-muted-foreground">
              ({status.tool})
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 mt-0.5">
          <div className="flex-1 h-1 bg-muted rounded-full overflow-hidden max-w-[120px]">
            <div
              className="h-full bg-primary/60 rounded-full transition-all duration-300"
              style={{ width: `${(status.iteration / status.maxIterations) * 100}%` }}
            />
          </div>
          <span className="text-xs text-muted-foreground">
            Step {status.iteration}/{status.maxIterations}
          </span>
        </div>
      </div>
    </div>
  )
}
