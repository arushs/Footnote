import { FileText, Search, ExternalLink, ChevronRight } from 'lucide-react'
import * as ScrollArea from '@radix-ui/react-scroll-area'
import type { Citation } from '../../types'
import { cn } from '../../lib/utils'

interface SourcesPanelProps {
  searchedFiles: string[]
  citedSources: Citation[]
  onSourceClick?: (citation: Citation) => void
}

export function SourcesPanel({ searchedFiles, citedSources, onSourceClick }: SourcesPanelProps) {
  const hasSources = searchedFiles.length > 0 || citedSources.length > 0

  return (
    <aside className="w-72 border-l border-border flex flex-col bg-background">
      <div className="p-4 border-b border-border">
        <h2 className="font-semibold text-foreground">Sources</h2>
      </div>

      <ScrollArea.Root className="flex-1 overflow-hidden">
        <ScrollArea.Viewport className="h-full w-full p-4">
          {!hasSources ? (
            <div className="text-center py-8">
              <div className="mx-auto w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-3">
                <Search className="h-5 w-5 text-muted-foreground" />
              </div>
              <p className="text-sm text-muted-foreground">
                Sources will appear here when you ask a question
              </p>
            </div>
          ) : (
            <div className="space-y-6">
              {citedSources.length > 0 && (
                <section>
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
                    Cited Sources
                  </h3>
                  <div className="space-y-2">
                    {citedSources.map((citation, index) => (
                      <SourceCard
                        key={citation.chunk_id}
                        citation={citation}
                        number={index + 1}
                        onClick={() => onSourceClick?.(citation)}
                      />
                    ))}
                  </div>
                </section>
              )}

              {searchedFiles.length > 0 && (
                <section>
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-3">
                    Searched Files
                  </h3>
                  <div className="space-y-1">
                    {searchedFiles.map((fileName, index) => (
                      <div
                        key={index}
                        className="flex items-center gap-2 py-1.5 px-2 rounded text-sm text-muted-foreground"
                      >
                        <FileText className="h-4 w-4 shrink-0" />
                        <span className="truncate">{fileName}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar
          className="flex touch-none select-none bg-muted/50 p-0.5 transition-colors hover:bg-muted data-[orientation=vertical]:w-2.5"
          orientation="vertical"
        >
          <ScrollArea.Thumb className="relative flex-1 rounded-full bg-border" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>
    </aside>
  )
}

interface SourceCardProps {
  citation: Citation
  number: number
  onClick: () => void
}

function SourceCard({ citation, number, onClick }: SourceCardProps) {
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
