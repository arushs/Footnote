import { Plus } from 'lucide-react'
import * as ScrollArea from '@radix-ui/react-scroll-area'
import type { Conversation } from '../../types'
import { cn } from '../../lib/utils'
import { ConversationList } from './ConversationList'

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
  return (
    <aside className="w-64 border-r border-border flex flex-col bg-muted/30">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <h2 className="font-semibold text-foreground truncate">
          {folderName || 'Chat History'}
        </h2>
      </div>

      {/* New Chat Button */}
      <div className="p-3 border-b border-border">
        <button
          onClick={onNewConversation}
          className={cn(
            'w-full flex items-center gap-2 px-3 py-2 rounded-lg',
            'bg-primary text-primary-foreground',
            'hover:bg-primary/90 transition-colors',
            'text-sm font-medium'
          )}
        >
          <Plus className="h-4 w-4" />
          New Chat
        </button>
      </div>

      {/* Conversation List */}
      <ScrollArea.Root className="flex-1 overflow-hidden">
        <ScrollArea.Viewport className="h-full w-full">
          <ConversationList
            conversations={conversations}
            currentConversationId={currentConversationId}
            isLoading={isLoading}
            onSelectConversation={onSelectConversation}
          />
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
