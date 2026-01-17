import { MessageCircle } from 'lucide-react'
import * as ScrollArea from '@radix-ui/react-scroll-area'
import { ChatMessage } from './ChatMessage'
import { StreamingMessage } from './StreamingMessage'
import type { Message, Citation } from '../../types'

interface MessageListProps {
  messages: Message[]
  streamingContent?: string
  isLoading?: boolean
  onCitationClick?: (citation: Citation) => void
  isSourcesOpen?: boolean
  onToggleSources?: () => void
}

export function MessageList({
  messages,
  streamingContent,
  isLoading,
  onCitationClick,
  isSourcesOpen,
  onToggleSources,
}: MessageListProps) {

  // Show empty state only when not loading and no messages
  if (messages.length === 0 && !streamingContent && !isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="text-center space-y-4">
          <div className="mx-auto w-12 h-12 rounded-full bg-muted flex items-center justify-center">
            <MessageCircle className="h-6 w-6 text-muted-foreground" />
          </div>
          <div className="space-y-2">
            <h3 className="font-medium text-foreground">Start a conversation</h3>
            <p className="text-sm text-muted-foreground max-w-sm">
              Ask questions about your documents. The AI will search through your files
              and provide answers with citations.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <ScrollArea.Root className="flex-1 overflow-hidden">
      <ScrollArea.Viewport className="h-full w-full">
        <div className="divide-y divide-border" role="log" aria-live="polite" aria-label="Chat messages">
          {messages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              onCitationClick={onCitationClick}
              isSourcesOpen={isSourcesOpen}
              onToggleSources={onToggleSources}
            />
          ))}
          {isLoading && streamingContent && (
            <StreamingMessage content={streamingContent} />
          )}
          {isLoading && !streamingContent && (
            <div className="flex gap-3 px-4 py-4 bg-background" role="status" aria-label="Generating response">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
                <div className="flex gap-1" aria-hidden="true">
                  <span className="w-1.5 h-1.5 bg-foreground rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-1.5 h-1.5 bg-foreground rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-1.5 h-1.5 bg-foreground rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
        </div>
      </ScrollArea.Viewport>
      <ScrollArea.Scrollbar
        className="flex touch-none select-none bg-muted/50 p-0.5 transition-colors hover:bg-muted data-[orientation=horizontal]:h-2.5 data-[orientation=vertical]:w-2.5 data-[orientation=horizontal]:flex-col"
        orientation="vertical"
      >
        <ScrollArea.Thumb className="relative flex-1 rounded-full bg-border" />
      </ScrollArea.Scrollbar>
    </ScrollArea.Root>
  )
}
