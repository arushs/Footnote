import { ExternalLink, ChevronRight } from 'lucide-react'
import type { Citation } from '../../types'
import { cn } from '../../lib/utils'

export interface SourceCardProps {
  citation: Citation
  number: number
  onClick: () => void
}

/**
 * SourceCard displays a citation with file name, location, and excerpt.
 * Clicking opens the source in detail, external link opens Google Drive.
 */
export function SourceCard({ citation, number, onClick }: SourceCardProps) {
  const handleOpenInDrive = (e: React.MouseEvent) => {
    e.stopPropagation()
    window.open(citation.google_drive_url, '_blank', 'noopener,noreferrer')
  }

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left rounded-lg border border-border p-3 transition-colors',
        'hover:bg-muted/50 focus:outline-none focus:ring-2 focus:ring-ring'
      )}
    >
      <div className="flex items-start gap-2">
        <span className="flex h-5 min-w-5 items-center justify-center rounded bg-primary/10 text-primary text-xs font-medium">
          {number}
        </span>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="font-medium text-sm truncate">{citation.file_name}</span>
            <button
              onClick={handleOpenInDrive}
              className="shrink-0 p-1 rounded hover:bg-muted transition-colors"
              title="Open in Google Drive"
            >
              <ExternalLink className="h-3 w-3 text-muted-foreground" />
            </button>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5">{citation.location}</p>
          <p className="text-xs text-muted-foreground mt-1 line-clamp-2 italic">
            "{citation.excerpt}"
          </p>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
      </div>
    </button>
  )
}
