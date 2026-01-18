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
    <div className="flex items-center gap-3 px-4 py-3">
      <div className={`flex items-center justify-center ${config.color}`}>
        <Icon className="h-4 w-4 animate-spin" />
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">
          {config.label}
          {status.tool && status.phase !== 'generating' && (
            <span className="text-muted-foreground/70">
              {' '}· {status.tool}
            </span>
          )}
        </span>
      </div>
    </div>
  )
}
