import { useState, useEffect } from 'react'
import { FolderOpen, ChevronDown, Loader2, Plus, Clock } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useNavigate, useParams } from 'react-router-dom'
import { useGooglePicker } from '../../hooks'
import { addToast } from '../ui/toast'
import { cn } from '../../lib/utils'
import type { Folder } from '../../types'

interface FolderDropdownProps {
  currentFolderName?: string
}

export function FolderDropdown({ currentFolderName }: FolderDropdownProps) {
  const navigate = useNavigate()
  const { folderId } = useParams<{ folderId: string }>()
  const { isLoaded, isConfigured, openPicker } = useGooglePicker()
  const [folders, setFolders] = useState<Folder[]>([])
  const [loading, setLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)

  useEffect(() => {
    fetch('/api/folders', { credentials: 'include' })
      .then((r) => r.json())
      .then((data) => setFolders(data.folders))
      .catch(() => addToast('Failed to load folders', 'error'))
      .finally(() => setLoading(false))
  }, [])

  const formatLastSynced = (dateString: string | null) => {
    if (!dateString) return 'Never synced'
    const date = new Date(dateString)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    if (diffDays < 7) return `${diffDays}d ago`
    return date.toLocaleDateString()
  }

  const handleAddFolder = async () => {
    if (!isConfigured || !isLoaded) {
      addToast('Google Drive integration not ready', 'error')
      return
    }
    try {
      const result = await openPicker()
      if (!result) return

      setIsCreating(true)
      const response = await fetch('/api/folders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          google_folder_id: result.id,
          folder_name: result.name,
        }),
      })

      if (response.ok) {
        const newFolder = await response.json()
        addToast(`Added folder "${result.name}"`, 'success')
        navigate(`/chat/${newFolder.id}`)
      } else {
        const error = await response.json().catch(() => ({}))
        addToast(error.detail || 'Failed to add folder', 'error')
      }
    } catch {
      addToast('Failed to add folder', 'error')
    } finally {
      setIsCreating(false)
    }
  }

  const readyFolders = folders.filter((f) => f.index_status === 'ready')
  const indexingFolders = folders.filter((f) => f.index_status === 'indexing')

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className={cn(
            'flex items-center gap-1.5 px-2 py-1 -ml-2 rounded-md transition-colors',
            'hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring',
            'text-foreground'
          )}
          aria-label="Switch folder"
        >
          <span className="font-semibold truncate max-w-[140px]">
            {currentFolderName || 'Select folder'}
          </span>
          <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className={cn(
            'min-w-[240px] max-w-[280px] rounded-lg bg-popover p-1 shadow-lg',
            'border border-border',
            'animate-in fade-in-0 zoom-in-95',
            'data-[side=bottom]:slide-in-from-top-2'
          )}
          sideOffset={5}
          align="start"
        >
          {loading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <>
              {/* Ready folders */}
              {readyFolders.length > 0 && (
                <DropdownMenu.Label className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                  Your folders
                </DropdownMenu.Label>
              )}
              {readyFolders.map((folder) => (
                <DropdownMenu.Item
                  key={folder.id}
                  className={cn(
                    'flex items-start gap-2 px-2 py-2 rounded-md cursor-pointer',
                    'text-sm outline-none',
                    'focus:bg-accent focus:text-accent-foreground',
                    folder.id === folderId && 'bg-muted'
                  )}
                  onSelect={() => navigate(`/chat/${folder.id}`)}
                >
                  <FolderOpen className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate text-foreground">
                      {folder.folder_name}
                    </p>
                    <div className="flex items-center gap-1 mt-0.5">
                      <Clock className="h-3 w-3 text-muted-foreground" />
                      <span className="text-xs text-muted-foreground">
                        {formatLastSynced(folder.last_synced_at)}
                      </span>
                    </div>
                  </div>
                </DropdownMenu.Item>
              ))}

              {/* Indexing folders */}
              {indexingFolders.length > 0 && (
                <>
                  {readyFolders.length > 0 && (
                    <DropdownMenu.Separator className="h-px bg-border my-1" />
                  )}
                  <DropdownMenu.Label className="px-2 py-1.5 text-xs font-medium text-muted-foreground">
                    Indexing...
                  </DropdownMenu.Label>
                  {indexingFolders.map((folder) => (
                    <DropdownMenu.Item
                      key={folder.id}
                      className={cn(
                        'flex items-center gap-2 px-2 py-2 rounded-md',
                        'text-sm text-muted-foreground opacity-60'
                      )}
                      disabled
                    >
                      <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
                      <span className="truncate">{folder.folder_name}</span>
                    </DropdownMenu.Item>
                  ))}
                </>
              )}

              {/* Add new folder */}
              <DropdownMenu.Separator className="h-px bg-border my-1" />
              <DropdownMenu.Item
                className={cn(
                  'flex items-center gap-2 px-2 py-2 rounded-md cursor-pointer',
                  'text-sm text-foreground outline-none',
                  'focus:bg-accent focus:text-accent-foreground',
                  'data-[disabled]:pointer-events-none data-[disabled]:opacity-50'
                )}
                onSelect={handleAddFolder}
                disabled={!isConfigured || !isLoaded || isCreating}
              >
                {isCreating ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                <span>Add new folder</span>
              </DropdownMenu.Item>
            </>
          )}
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
