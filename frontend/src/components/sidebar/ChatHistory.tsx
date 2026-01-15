import { Plus, MessageSquare, Clock } from 'lucide-react'
import * as ScrollArea from '@radix-ui/react-scroll-area'
import type { Conversation } from '../../types'
import { cn } from '../../lib/utils'
import { AddFolderDropdown } from './AddFolderDropdown'

interface ChatHistoryProps {
  conversations: Conversation[]
  currentConversationId: string | null
  folderName?: string
  isLoading?: boolean
  onSelectConversation: (id: string) => void
  onNewConversation: () => void
}

export function ChatHistory({
  conversations,
  currentConversationId,
  folderName,
  isLoading,
  onSelectConversation,
  onNewConversation,
}: ChatHistoryProps) {
  const formatDate = (dateString: string) => {
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

  return (
    <aside className="w-64 border-r border-border flex flex-col bg-muted/30" aria-label="Chat history">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between gap-2">
          <h2 className="font-semibold text-foreground truncate flex-1">
            {folderName || 'Chat History'}
          </h2>
          <AddFolderDropdown />
        </div>
      </div>

      {/* New Chat Button */}
      <div className="p-3 border-b border-border">
        <button
          onClick={onNewConversation}
          className={cn(
            'w-full flex items-center gap-2 px-3 py-2 rounded-lg',
            'bg-primary text-primary-foreground',
            'hover:bg-primary/90 transition-colors',
            'text-sm font-medium',
            'focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2'
          )}
        >
          <Plus className="h-4 w-4" aria-hidden="true" />
          New Chat
        </button>
      </div>

      {/* Conversation List */}
      <ScrollArea.Root className="flex-1 overflow-hidden">
        <ScrollArea.Viewport className="h-full w-full">
          <div className="p-2 space-y-1">
            {isLoading ? (
              <div className="space-y-2 p-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="animate-pulse">
                    <div className="h-4 bg-muted rounded w-3/4 mb-2" />
                    <div className="h-3 bg-muted rounded w-1/2" />
                  </div>
                ))}
              </div>
            ) : conversations.length === 0 ? (
              <div className="text-center py-8 px-4">
                <MessageSquare className="h-8 w-8 text-muted-foreground mx-auto mb-2" aria-hidden="true" />
                <p className="text-sm text-muted-foreground">
                  No conversations yet
                </p>
              </div>
            ) : (
              conversations.map((conversation) => (
                <ConversationItem
                  key={conversation.id}
                  conversation={conversation}
                  isActive={conversation.id === currentConversationId}
                  onClick={() => onSelectConversation(conversation.id)}
                  formatDate={formatDate}
                />
              ))
            )}
          </div>
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

interface ConversationItemProps {
  conversation: Conversation
  isActive: boolean
  onClick: () => void
  formatDate: (date: string) => string
}

function ConversationItem({
  conversation,
  isActive,
  onClick,
  formatDate,
}: ConversationItemProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left px-3 py-2.5 rounded-lg transition-colors',
        'hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring',
        isActive ? 'bg-muted' : ''
      )}
      aria-current={isActive ? 'true' : undefined}
      aria-label={`${conversation.preview || 'New conversation'}, ${formatDate(conversation.created_at)}`}
    >
      <p className="text-sm font-medium text-foreground line-clamp-1">
        {conversation.preview || 'New conversation'}
      </p>
      <div className="flex items-center gap-1 mt-1">
        <Clock className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
        <span className="text-xs text-muted-foreground">
          {formatDate(conversation.created_at)}
        </span>
      </div>
    </button>
  )
}
