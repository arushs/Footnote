import { MessageSquare, Clock } from 'lucide-react'
import type { Conversation } from '../../types'
import { cn } from '../../lib/utils'

export interface ConversationListProps {
  conversations: Conversation[]
  currentConversationId: string | null
  isLoading?: boolean
  onSelectConversation: (id: string) => void
}

/**
 * ConversationList displays a list of conversations with selection state.
 */
export function ConversationList({
  conversations,
  currentConversationId,
  isLoading,
  onSelectConversation,
}: ConversationListProps) {
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

  if (isLoading) {
    return (
      <div className="space-y-2 p-2">
        {[1, 2, 3].map((i) => (
          <div key={i} className="animate-pulse">
            <div className="h-4 bg-muted rounded w-3/4 mb-2" />
            <div className="h-3 bg-muted rounded w-1/2" />
          </div>
        ))}
      </div>
    )
  }

  if (conversations.length === 0) {
    return (
      <div className="text-center py-8 px-4">
        <MessageSquare className="h-8 w-8 text-muted-foreground mx-auto mb-2" />
        <p className="text-sm text-muted-foreground">
          No conversations yet
        </p>
      </div>
    )
  }

  return (
    <div className="p-2 space-y-1">
      {conversations.map((conversation) => (
        <ConversationItem
          key={conversation.id}
          conversation={conversation}
          isActive={conversation.id === currentConversationId}
          onClick={() => onSelectConversation(conversation.id)}
          formatDate={formatDate}
        />
      ))}
    </div>
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
    >
      <p className="text-sm font-medium text-foreground line-clamp-1">
        {conversation.preview || 'New conversation'}
      </p>
      <div className="flex items-center gap-1 mt-1">
        <Clock className="h-3 w-3 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">
          {formatDate(conversation.created_at)}
        </span>
      </div>
    </button>
  )
}
