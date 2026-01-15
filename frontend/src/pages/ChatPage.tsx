import { useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { MessageList, MessageInput } from '../components/chat'
import { ChatHistory } from '../components/sidebar'
import { SourcesPanel } from '../components/sources'
import { IndexingProgress, IndexingComplete } from '../components/overlay'
import { useChat, useConversations, useFolderStatus } from '../hooks'
import type { Citation } from '../types'

export function ChatPage() {
  const { folderId } = useParams<{ folderId: string }>()
  const [searchedFiles, setSearchedFiles] = useState<string[]>([])
  const [citedSources, setCitedSources] = useState<Citation[]>([])
  const [showIndexingComplete, setShowIndexingComplete] = useState(false)

  // Handle indexing complete transition
  const handleIndexingComplete = useCallback(() => {
    setShowIndexingComplete(true)
  }, [])

  // Folder status for indexing overlay
  const { folder, status, isIndexing } = useFolderStatus({
    folderId: folderId!,
    onIndexingComplete: handleIndexingComplete,
  })

  // Conversations for sidebar
  const {
    conversations,
    isLoading: conversationsLoading,
    refetch: refetchConversations,
  } = useConversations({ folderId: folderId! })

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

  // Chat state and actions
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
    folderId: folderId!,
    onSourcesUpdate: handleSourcesUpdate,
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

  return (
    <div className="min-h-screen flex bg-background relative">
      {/* Indexing overlay */}
      {status && isIndexing && (
        <IndexingProgress status={status} folderName={folder?.folder_name} />
      )}

      {/* Indexing complete overlay */}
      {showIndexingComplete && (
        <IndexingComplete onDismiss={() => setShowIndexingComplete(false)} />
      )}

      {/* Left sidebar - Chat History */}
      <ChatHistory
        conversations={conversations}
        currentConversationId={currentConversationId}
        folderName={folder?.folder_name}
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
  )
}
