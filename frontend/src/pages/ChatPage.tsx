import { useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import { FolderOpen, ArrowRight } from 'lucide-react'
import { MessageList, MessageInput } from '../components/chat'
import { ChatHistory } from '../components/sidebar'
import { SourcesPanel } from '../components/sources'
import { IndexingProgress, IndexingComplete } from '../components/overlay'
import { AppShell } from '../components/layout/AppShell'
import { Header, UserMenu } from '../components/layout/Header'
import { useChat, useConversations, useFolderStatus } from '../hooks'
import type { Citation } from '../types'

function EmptyState() {
  return (
    <div className="flex-1 flex items-center justify-center bg-background">
      <div className="text-center max-w-md px-6">
        <div className="mx-auto w-16 h-16 rounded-full bg-muted flex items-center justify-center mb-6">
          <FolderOpen className="w-8 h-8 text-muted-foreground" />
        </div>
        <h2 className="text-2xl font-semibold text-foreground mb-2">
          No folder selected
        </h2>
        <p className="text-muted-foreground mb-6">
          Select a Google Drive folder to start chatting with your documents.
        </p>
        <Link
          to="/folders"
          className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg hover:bg-primary/90 transition-colors"
        >
          Browse folders
          <ArrowRight className="w-4 h-4" />
        </Link>
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
