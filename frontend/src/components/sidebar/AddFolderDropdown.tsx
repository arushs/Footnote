import { useState } from 'react'
import { Plus, FolderPlus, Loader2 } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { useNavigate } from 'react-router-dom'
import { useGooglePicker } from '../../hooks'
import { addToast } from '../ui/toast'
import { apiUrl } from '../../config/api'
import { cn } from '../../lib/utils'

interface AddFolderDropdownProps {
  className?: string
}

export function AddFolderDropdown({ className }: AddFolderDropdownProps) {
  const navigate = useNavigate()
  const { isLoaded, isConfigured, openPicker } = useGooglePicker()
  const [isCreating, setIsCreating] = useState(false)

  const handleAddGoogleDriveFolder = async () => {
    if (!isConfigured) {
      addToast('Google Drive integration not configured', 'error')
      return
    }
    if (!isLoaded) {
      addToast('Google APIs still loading, please wait...', 'error')
      return
    }

    try {
      const result = await openPicker()
      if (!result) return

      setIsCreating(true)
      const response = await fetch(apiUrl('/api/folders'), {
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
        // Navigate to the new folder's chat
        navigate(`/chat/${newFolder.id}`)
      } else {
        const error = await response.json().catch(() => ({}))
        addToast(error.detail || 'Failed to add folder', 'error')
      }
    } catch (error) {
      console.error('Failed to create folder:', error)
      addToast('Failed to add folder', 'error')
    } finally {
      setIsCreating(false)
    }
  }

  return (
    <DropdownMenu.Root>
      <DropdownMenu.Trigger asChild>
        <button
          className={cn(
            'p-1.5 rounded-md transition-colors',
            'hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring',
            'text-muted-foreground hover:text-foreground',
            className
          )}
          aria-label="Add folder"
          disabled={isCreating}
        >
          {isCreating ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <Plus className="h-4 w-4" aria-hidden="true" />
          )}
        </button>
      </DropdownMenu.Trigger>

      <DropdownMenu.Portal>
        <DropdownMenu.Content
          className={cn(
            'min-w-[200px] rounded-md bg-popover p-1 shadow-md',
            'border border-border',
            'animate-in fade-in-0 zoom-in-95',
            'data-[side=bottom]:slide-in-from-top-2',
            'data-[side=top]:slide-in-from-bottom-2'
          )}
          sideOffset={5}
          align="end"
        >
          <DropdownMenu.Item
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-sm cursor-pointer',
              'text-sm text-foreground',
              'outline-none focus:bg-accent focus:text-accent-foreground',
              'data-[disabled]:pointer-events-none data-[disabled]:opacity-50'
            )}
            onSelect={handleAddGoogleDriveFolder}
            disabled={!isConfigured || !isLoaded || isCreating}
          >
            <FolderPlus className="h-4 w-4" aria-hidden="true" />
            <span>Add Google Drive Folder</span>
          </DropdownMenu.Item>
        </DropdownMenu.Content>
      </DropdownMenu.Portal>
    </DropdownMenu.Root>
  )
}
