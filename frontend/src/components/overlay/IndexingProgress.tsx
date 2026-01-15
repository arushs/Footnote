import { Loader2, FileSearch, CheckCircle2, XCircle } from 'lucide-react'
import type { FolderStatus } from '../../types'

interface IndexingProgressProps {
  status: FolderStatus
  folderName?: string
}

export function IndexingProgress({ status, folderName }: IndexingProgressProps) {
  const progress = status.files_total > 0
    ? Math.round((status.files_indexed / status.files_total) * 100)
    : 0

  const isComplete = status.status === 'ready'
  const isFailed = status.status === 'failed'

  if (isComplete) return null

  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-xl shadow-lg p-8 max-w-md w-full mx-4">
        <div className="text-center space-y-6">
          {/* Icon */}
          <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center">
            {isFailed ? (
              <XCircle className="h-8 w-8 text-destructive" />
            ) : (
              <FileSearch className="h-8 w-8 text-primary" />
            )}
          </div>

          {/* Title */}
          <div className="space-y-2">
            <h2 className="text-xl font-semibold text-foreground">
              {isFailed ? 'Indexing Failed' : 'Indexing Your Files'}
            </h2>
            {folderName && (
              <p className="text-sm text-muted-foreground">{folderName}</p>
            )}
          </div>

          {/* Progress */}
          {!isFailed && (
            <div className="space-y-3">
              {/* Progress bar */}
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-300 ease-out"
                  style={{ width: `${progress}%` }}
                />
              </div>

              {/* Progress text */}
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                <span>
                  {status.files_indexed} of {status.files_total} files indexed
                </span>
              </div>
            </div>
          )}

          {/* Status message */}
          <p className="text-sm text-muted-foreground">
            {isFailed
              ? 'There was an error indexing your files. Please try again.'
              : status.status === 'pending'
              ? 'Preparing to index your documents...'
              : 'Please wait while we process your documents. This may take a few minutes.'}
          </p>

          {/* Failed action */}
          {isFailed && (
            <button
              onClick={() => window.location.reload()}
              className="inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
            >
              Try Again
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

interface IndexingCompleteProps {
  onDismiss: () => void
}

export function IndexingComplete({ onDismiss }: IndexingCompleteProps) {
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-background/80 backdrop-blur-sm animate-in fade-in">
      <div className="bg-card border border-border rounded-xl shadow-lg p-8 max-w-md w-full mx-4 animate-in zoom-in-95">
        <div className="text-center space-y-6">
          <div className="mx-auto w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center">
            <CheckCircle2 className="h-8 w-8 text-green-500" />
          </div>

          <div className="space-y-2">
            <h2 className="text-xl font-semibold text-foreground">
              Indexing Complete!
            </h2>
            <p className="text-sm text-muted-foreground">
              Your documents are ready. Start asking questions!
            </p>
          </div>

          <button
            onClick={onDismiss}
            className="inline-flex items-center justify-center rounded-md bg-primary px-6 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Start Chatting
          </button>
        </div>
      </div>
    </div>
  )
}
