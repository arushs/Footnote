# feat: Chat Page Folder Selection with View Toggle

## Overview

Add a toggle in the sidebar to switch between chat history and folder view. Users can view synced folders and remove ones they no longer need—all without leaving the chat page.

**Scope:** Minimal changes to existing files. No new component files.

## Problem Statement

Users cannot view/manage all synced folders from within the chat interface. They need to:
- See all synced folders at a glance
- Switch between folder contexts
- Remove folders they no longer need

## Proposed Solution

### 1. Sidebar View Toggle

Add toggle buttons in `ChatHistory` header:

```
┌─────────────────────────────────────────┐
│  [Chats] [Folders]                 [+]  │  ← Toggle buttons
├─────────────────────────────────────────┤
│  Conversation 1  (or)  Folder 1    [⋮]  │
│  Conversation 2        Folder 2    [⋮]  │
└─────────────────────────────────────────┘
```

### 2. Folder View

When "Folders" is active, show folder list with:
- Folder name
- Status badge (Ready / Indexing)
- Menu with "Remove" option

### 3. Folder Removal

Click menu → Remove → Confirm dialog → DELETE API → Refresh list

## Technical Approach

### Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/components/sidebar/ChatHistory.tsx` | Add toggle state, folder list rendering, delete handler (~60-80 lines) |
| `backend/app/routes/folders.py` | Add DELETE endpoint (~20 lines) |

**No new files required.**

### Backend: DELETE Endpoint

```python
# backend/app/routes/folders.py

@router.delete("/{folder_id}")
async def delete_folder(
    folder_id: str,
    session: DbSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a folder and all associated data."""
    # Parse UUID (folder_id comes as string from path)
    try:
        folder_uuid = uuid.UUID(folder_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid folder ID")

    # Fetch folder with ownership check
    result = await db.execute(
        select(Folder).where(
            Folder.id == folder_uuid,
            Folder.user_id == session.user_id,
        )
    )
    folder = result.scalar_one_or_none()

    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Block deletion while indexing
    if folder.index_status == "indexing":
        raise HTTPException(
            status_code=409,
            detail="Cannot delete folder while indexing is in progress"
        )

    # Cascade delete handles conversations, messages, files, chunks
    await db.delete(folder)
    await db.commit()

    return {"success": True, "folder_id": folder_id}
```

### Frontend: ChatHistory.tsx Changes

```tsx
// frontend/src/components/sidebar/ChatHistory.tsx

export function ChatHistory({ folderId, ... }: ChatHistoryProps) {
  // Existing state...

  // NEW: Toggle and folders state
  const [showFolders, setShowFolders] = useState(false)
  const [folders, setFolders] = useState<Folder[]>([])
  const [foldersLoading, setFoldersLoading] = useState(false)

  // NEW: Fetch folders when toggled to folder view
  useEffect(() => {
    if (showFolders) {
      setFoldersLoading(true)
      fetch('/api/folders', { credentials: 'include' })
        .then(r => r.json())
        .then(data => setFolders(data.folders))
        .catch(console.error)
        .finally(() => setFoldersLoading(false))
    }
  }, [showFolders])

  // NEW: Delete folder handler
  const handleDeleteFolder = async (id: string, name: string) => {
    if (!confirm(`Remove "${name}"?\n\nThis will delete all conversations and chat history.`)) {
      return
    }

    try {
      const res = await fetch(`/api/folders/${id}`, {
        method: 'DELETE',
        credentials: 'include',
      })
      if (!res.ok) {
        const error = await res.json()
        throw new Error(error.detail || 'Failed to delete folder')
      }
      // Refresh folder list
      setFolders(folders.filter(f => f.id !== id))
      // If deleted current folder, navigate away
      if (id === folderId) {
        navigate('/chat')
      }
    } catch (err) {
      alert((err as Error).message)
    }
  }

  // NEW: Handle folder selection
  const handleSelectFolder = (id: string) => {
    navigate(`/chat/${id}`)
    setShowFolders(false) // Switch back to chats view
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header with toggle */}
      <div className="p-3 border-b flex items-center gap-2">
        <div className="flex bg-muted rounded-lg p-0.5 flex-1">
          <button
            className={cn(
              "flex-1 px-3 py-1 text-sm rounded-md transition-colors",
              !showFolders ? "bg-background shadow-sm" : "text-muted-foreground"
            )}
            onClick={() => setShowFolders(false)}
          >
            Chats
          </button>
          <button
            className={cn(
              "flex-1 px-3 py-1 text-sm rounded-md transition-colors",
              showFolders ? "bg-background shadow-sm" : "text-muted-foreground"
            )}
            onClick={() => setShowFolders(true)}
          >
            Folders
          </button>
        </div>
        <AddFolderDropdown />
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        {showFolders ? (
          // Folder list view
          foldersLoading ? (
            <div className="p-4 text-center text-muted-foreground">Loading...</div>
          ) : folders.length === 0 ? (
            <div className="p-4 text-center text-muted-foreground text-sm">
              No folders synced yet.
            </div>
          ) : (
            <div className="flex flex-col gap-1 p-2">
              {folders.map(folder => (
                <div
                  key={folder.id}
                  className={cn(
                    "flex items-center gap-2 p-2 rounded-md cursor-pointer hover:bg-muted",
                    folder.id === folderId && "bg-muted"
                  )}
                  onClick={() => folder.index_status === 'ready' && handleSelectFolder(folder.id)}
                >
                  <FolderIcon className="w-4 h-4 text-muted-foreground" />
                  <div className="flex-1 min-w-0">
                    <div className="truncate text-sm">{folder.folder_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {folder.files_indexed} / {folder.files_total} files
                    </div>
                  </div>
                  <Badge variant={folder.index_status === 'ready' ? 'secondary' : 'outline'}>
                    {folder.index_status === 'ready' ? 'Ready' : 'Indexing'}
                  </Badge>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon" className="h-8 w-8">
                        <MoreVertical className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent>
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={(e) => {
                          e.stopPropagation()
                          handleDeleteFolder(folder.id, folder.folder_name)
                        }}
                      >
                        Remove folder
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>
              ))}
            </div>
          )
        ) : (
          // Existing conversation list
          <>
            <div className="p-2">
              <Button onClick={onNewConversation} className="w-full">
                + New Chat
              </Button>
            </div>
            {/* ... existing ConversationList rendering ... */}
          </>
        )}
      </ScrollArea>
    </div>
  )
}
```

## Acceptance Criteria

- [ ] Toggle in sidebar switches between "Chats" and "Folders" views
- [ ] Folder view shows all synced folders with name, file count, and status
- [ ] Clicking a ready folder navigates to `/chat/{folderId}` and switches to chats view
- [ ] Indexing folders show status but are not clickable
- [ ] Folder menu has "Remove folder" option
- [ ] Remove shows browser confirm dialog
- [ ] Confirming removal deletes folder via API
- [ ] Removing current folder redirects to `/chat`
- [ ] Add button (+) works from both views

## What We're NOT Doing (YAGNI)

- ~~localStorage persistence for toggle state~~ - Default to chats is fine
- ~~Separate ViewToggle component~~ - Inline is simpler
- ~~Separate FolderList/FolderItem components~~ - Inline is simpler
- ~~useFolders hook~~ - Inline fetch is simpler
- ~~Retry for failed folders~~ - Not requested
- ~~Keyboard navigation~~ - Browser defaults work
- ~~Full ARIA tablist semantics~~ - Simple buttons suffice

## References

### Internal Files
- `frontend/src/components/sidebar/ChatHistory.tsx` - Main file to modify
- `frontend/src/pages/ChatPage.tsx:23-28` - Existing folder fetch pattern to copy
- `backend/app/routes/folders.py` - Add DELETE endpoint here
- `backend/app/models/db_models.py:37-53` - Folder model (has cascade delete)

### Existing Patterns
- `AddFolderDropdown.tsx:36` - Shows `credentials: 'include'` pattern
- `folders.py:126-156` - Shows UUID parsing pattern for folder endpoints
