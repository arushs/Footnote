import { useState, useCallback, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { FolderOpen, ChevronDown, Loader2, Plus } from 'lucide-react'
import * as DropdownMenu from '@radix-ui/react-dropdown-menu'
import { MessageList, MessageInput } from '../components/chat'
import { ChatHistory } from '../components/sidebar'
import { SourcesPanel } from '../components/sources'
import { IndexingProgress, IndexingComplete } from '../components/overlay'
import { AppShell } from '../components/layout/AppShell'
import { Header, UserMenu } from '../components/layout/Header'
import { useChat, useConversations, useFolderStatus, useGooglePicker } from '../hooks'
import type { Citation, Folder } from '../types'
import { cn } from '../lib/utils'
import { addToast } from '../components/ui/toast'

function EmptyState() {
  const navigate = useNavigate()
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
    <div className="flex-1 flex items-center justify-center bg-background">
      <div className="text-center max-w-md px-6">
        <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-6">
          <FolderOpen className="w-8 h-8 text-muted-foreground" />
        </div>
        <h2 className="text-2xl font-semibold text-foreground mb-2">
          How can I help you?
        </h2>
        <p className="text-muted-foreground mb-6">
          Select a folder to start chatting with your documents.
        </p>

        {loading ? (
          <Loader2 className="h-6 w-6 animate-spin mx-auto text-muted-foreground" />
        ) : (
          <div className="space-y-3">
            {folders.length > 0 && (
              <DropdownMenu.Root>
                <DropdownMenu.Trigger asChild>
                  <button
                    className={cn(
                      'w-full flex items-center justify-between gap-2 px-4 py-3',
                      'bg-muted/50 border border-border rounded-lg',
                      'text-foreground hover:bg-muted transition-colors',
                      'focus:outline-none focus:ring-2 focus:ring-ring'
                    )}
                  >
                    <span className="text-muted-foreground">Select a folder...</span>
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  </button>
                </DropdownMenu.Trigger>

                <DropdownMenu.Portal>
                  <DropdownMenu.Content
                    className={cn(
                      'min-w-[280px] rounded-lg bg-popover p-1 shadow-lg',
                      'border border-border',
                      'animate-in fade-in-0 zoom-in-95'
                    )}
                    sideOffset={5}
                    align="center"
                  >
                    {readyFolders.map((folder) => (
                      <DropdownMenu.Item
                        key={folder.id}
                        className={cn(
                          'flex items-center gap-2 px-3 py-2 rounded-md cursor-pointer',
                          'text-sm text-foreground',
                          'outline-none focus:bg-accent focus:text-accent-foreground'
                        )}
                        onSelect={() => navigate(`/chat/${folder.id}`)}
                      >
                        <FolderOpen className="h-4 w-4 text-muted-foreground" />
                        <span className="truncate">{folder.folder_name}</span>
                      </DropdownMenu.Item>
                    ))}
                    {indexingFolders.length > 0 && (
                      <>
                        {readyFolders.length > 0 && (
                          <DropdownMenu.Separator className="h-px bg-border my-1" />
                        )}
                        <DropdownMenu.Label className="px-3 py-1.5 text-xs text-muted-foreground">
                          Indexing...
                        </DropdownMenu.Label>
                        {indexingFolders.map((folder) => (
                          <DropdownMenu.Item
                            key={folder.id}
                            className={cn(
                              'flex items-center gap-2 px-3 py-2 rounded-md',
                              'text-sm text-muted-foreground opacity-60'
                            )}
                            disabled
                          >
                            <Loader2 className="h-4 w-4 animate-spin" />
                            <span className="truncate">{folder.folder_name}</span>
                          </DropdownMenu.Item>
                        ))}
                      </>
                    )}
                  </DropdownMenu.Content>
                </DropdownMenu.Portal>
              </DropdownMenu.Root>
            )}

            <button
              onClick={handleAddFolder}
              disabled={isCreating || !isConfigured}
              className={cn(
                'w-full flex items-center justify-center gap-2 px-4 py-3',
                'bg-primary text-primary-foreground rounded-lg',
                'hover:bg-primary/90 transition-colors',
                'disabled:opacity-50 disabled:cursor-not-allowed'
              )}
            >
              {isCreating ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              <span>Add a Google Drive folder</span>
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

export function ChatPage() {
  const { folderId } = useParams<{ folderId: string }>()
  const [searchedFiles, setSearchedFiles] = useState<string[]>([])
  const [citedSources, setCitedSources] = useState<Citation[]>([])
  const [showIndexingComplete, setShowIndexingComplete] = useState(false)

  // Handle indexing complete transition
  const handleIndexingComplete = useCallback(() => {
    setShowIndexingComplete(true)
  }, [])

  // Folder status for indexing overlay (only when folderId exists)
  const { folder, status, isIndexing } = useFolderStatus({
    folderId: folderId || '',
    onIndexingComplete: handleIndexingComplete,
    enabled: !!folderId,
  })

  // Conversations for sidebar (only when folderId exists)
  const {
    conversations,
    isLoading: conversationsLoading,
    refetch: refetchConversations,
  } = useConversations({ folderId: folderId || '', enabled: !!folderId })

  // Handle sources update from chat
  const handleSourcesUpdate = useCallback(
    (files: string[], citations: Record<string, Citation>) => {
      setSearchedFiles(files)
      setCitedSources(Object.values(citations))
      // Refresh conversations list after a new message
      refetchConversations()
    },
    [refetchConversations]
  )

  // Chat state and actions (only when folderId exists)
  const {
    messages,
    isLoading: chatLoading,
    streamingContent,
    currentConversationId,
    sendMessage,
    stopGeneration,
    loadConversation,
    startNewConversation,
  } = useChat({
    folderId: folderId || '',
    onSourcesUpdate: handleSourcesUpdate,
    enabled: !!folderId,
  })

  // Handle citation click - open in Google Drive
  const handleCitationClick = useCallback((citation: Citation) => {
    window.open(citation.google_drive_url, '_blank', 'noopener,noreferrer')
  }, [])

  // Handle new conversation
  const handleNewConversation = useCallback(() => {
    startNewConversation()
    setSearchedFiles([])
    setCitedSources([])
  }, [startNewConversation])

  // Handle conversation select
  const handleSelectConversation = useCallback(
    (conversationId: string) => {
      loadConversation(conversationId)
      // Clear sources when switching conversations
      setSearchedFiles([])
      setCitedSources([])
    },
    [loadConversation]
  )

  // Show empty state when no folder is selected
  if (!folderId) {
    return (
      <AppShell>
        <Header>
          <Header.Brand title="Chat" backTo="/folders" backLabel="Folders" />
          <Header.Actions>
            <UserMenu />
          </Header.Actions>
        </Header>
        <EmptyState />
      </AppShell>
    )
  }

  return (
    <AppShell>
      {/* Header */}
      <Header>
        <Header.Brand title={folder?.folder_name || 'Chat'} backTo="/folders" backLabel="Folders" />
        <Header.Actions>
          <UserMenu />
        </Header.Actions>
      </Header>

      {/* Indexing overlay */}
      {status && isIndexing && (
        <IndexingProgress status={status} folderName={folder?.folder_name} />
      )}

      {/* Indexing complete overlay */}
      {showIndexingComplete && (
        <IndexingComplete onDismiss={() => setShowIndexingComplete(false)} />
      )}

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Left sidebar - Chat History */}
        <ChatHistory
          conversations={conversations}
          currentConversationId={currentConversationId}
          isLoading={conversationsLoading}
          onSelectConversation={handleSelectConversation}
          onNewConversation={handleNewConversation}
        />

        {/* Main chat area */}
        <main className="flex-1 flex flex-col min-w-0">
          <MessageList
            messages={messages}
            streamingContent={streamingContent}
            isLoading={chatLoading}
            onCitationClick={handleCitationClick}
          />
          <MessageInput
            onSend={sendMessage}
            onStop={stopGeneration}
            isLoading={chatLoading}
            disabled={isIndexing}
            placeholder={
              isIndexing
                ? 'Please wait for indexing to complete...'
                : 'Ask about your files...'
            }
          />
        </main>

        {/* Right sidebar - Sources */}
        <SourcesPanel
          searchedFiles={searchedFiles}
          citedSources={citedSources}
          onSourceClick={handleCitationClick}
        />
      </div>
    </AppShell>
  )
}
