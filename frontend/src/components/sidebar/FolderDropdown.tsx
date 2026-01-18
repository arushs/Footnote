import { FolderOpen, ChevronDown, Loader2, Plus, Clock } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useNavigate, useParams } from 'react-router-dom'
import { useFolders } from '../../hooks'
import { cn, formatRelativeTime } from '../../lib/utils'

interface FolderDropdownProps {
  currentFolderName?: string
}

export function FolderDropdown({ currentFolderName }: FolderDropdownProps) {
  const navigate = useNavigate()
  const { folderId } = useParams<{ folderId: string }>()
  const {
    readyFolders,
    indexingFolders,
    isLoading,
    isCreating,
    isReady,
    addFolder,
    refetch,
  } = useFolders()

  return (
    <DropdownMenu.Root onOpenChange={(open) => open && refetch()}>
      <DropdownMenu.Trigger asChild>
        <button
          className="flex items-center gap-1.5 px-2 py-1 -ml-2 rounded-md transition-colors hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring text-foreground"
          aria-label="Switch folder"
        >
          <span className="font-semibold truncate max-w-[140px]">
            {currentFolderName || 'Select folder'}
          </span>
          <ChevronDown className="h-4 w-4 text-muted-foreground flex-shrink-0" aria-hidden="true" />
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className="min-w-[240px] max-w-[280px] rounded-lg bg-popover p-1 shadow-lg border border-border animate-in fade-in-0 zoom-in-95 data-[side=bottom]:slide-in-from-top-2"
          sideOffset={5}
          align="start"
        >
          {isLoading ? (
            <div className="flex items-center justify-center py-4">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" aria-hidden="true" />
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
                    'flex items-start gap-2 px-2 py-2 rounded-md cursor-pointer text-sm outline-none focus:bg-accent focus:text-accent-foreground',
                    folder.id === folderId && 'bg-muted'
                  )}
                  onSelect={() => navigate(`/chat/${folder.id}`)}
                >
                  <FolderOpen className="h-4 w-4 text-muted-foreground mt-0.5 flex-shrink-0" aria-hidden="true" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium truncate text-foreground">
                      {folder.folder_name}
                    </p>
                    <div className="flex items-center gap-1 mt-0.5">
                      <Clock className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
                      <span className="text-xs text-muted-foreground">
                        {formatRelativeTime(folder.last_synced_at, 'Never synced')}
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
                      className="flex items-center gap-2 px-2 py-2 rounded-md text-sm text-muted-foreground opacity-60"
                      disabled
                    >
                      <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" aria-hidden="true" />
                      <span className="truncate">{folder.folder_name}</span>
                    </DropdownMenu.Item>
                  ))}
                </>
              )}

              {/* Add new folder */}
              <DropdownMenu.Separator className="h-px bg-border my-1" />
              <DropdownMenu.Item
                className="flex items-center gap-2 px-2 py-2 rounded-md cursor-pointer text-sm text-foreground outline-none focus:bg-accent focus:text-accent-foreground data-[disabled]:pointer-events-none data-[disabled]:opacity-50"
                onSelect={addFolder}
                disabled={!isReady || isCreating}
              >
                {isCreating ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Plus className="h-4 w-4" aria-hidden="true" />
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
