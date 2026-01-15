import { useState } from 'react'
import { Copy, Check, User, Bot } from 'lucide-react'
import * as Tooltip from '@radix-ui/react-tooltip'
import type { Message, Citation } from '../../types'
import { cn } from '../../lib/utils'

export interface ChatMessageProps {
  message: Message
  onCitationClick?: (citation: Citation) => void
}

export function ChatMessage({ message, onCitationClick }: ChatMessageProps) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Parse content and render citation markers
  const renderContent = () => {
    if (!message.citations || Object.keys(message.citations).length === 0) {
      return <p className="whitespace-pre-wrap">{message.content}</p>
    }

    // Find citation markers like [1], [2], etc. and replace with clickable elements
    const citationPattern = /\[(\d+)\]/g
    const parts: (string | JSX.Element)[] = []
    let lastIndex = 0
    let match

    while ((match = citationPattern.exec(message.content)) !== null) {
      // Add text before the citation
      if (match.index > lastIndex) {
        parts.push(message.content.slice(lastIndex, match.index))
      }

      const citationKey = match[1]
      const citation = message.citations[citationKey]

      if (citation) {
        parts.push(
          <CitationMarker
            key={`${match.index}-${citationKey}`}
            number={citationKey}
            citation={citation}
            onClick={() => onCitationClick?.(citation)}
          />
        )
      } else {
        parts.push(match[0])
      }

      lastIndex = match.index + match[0].length
    }

    // Add remaining text
    if (lastIndex < message.content.length) {
      parts.push(message.content.slice(lastIndex))
    }

    return <p className="whitespace-pre-wrap">{parts}</p>
  }

  return (
    <article
      className={cn(
        'group flex gap-3 px-4 py-4',
        isUser ? 'bg-muted/50' : 'bg-background'
      )}
      aria-label={isUser ? 'Your message' : 'Assistant response'}
    >
      <div
        className={cn(
          'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
          isUser ? 'bg-primary text-primary-foreground' : 'bg-secondary'
        )}
        aria-hidden="true"
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      <div className="flex-1 space-y-2 overflow-hidden">
        <div className="prose prose-sm max-w-none dark:prose-invert">
          {renderContent()}
        </div>
      </div>

      {!isUser && (
        <button
          onClick={handleCopy}
          className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity h-8 w-8 flex items-center justify-center rounded-md hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring"
          aria-label={copied ? 'Copied to clipboard' : 'Copy message'}
          title="Copy message"
        >
          {copied ? (
            <Check className="h-4 w-4 text-green-500" aria-hidden="true" />
          ) : (
            <Copy className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          )}
        </button>
      )}
    </article>
  )
}

interface CitationMarkerProps {
  number: string
  citation: Citation
  onClick: () => void
}

function CitationMarker({ number, citation, onClick }: CitationMarkerProps) {
  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button
            onClick={onClick}
            className="inline-flex items-center justify-center h-5 min-w-5 px-1 text-xs font-medium bg-primary/10 text-primary rounded hover:bg-primary/20 transition-colors mx-0.5 focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label={`Citation ${number}: ${citation.file_name}`}
          >
            {number}
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="z-50 max-w-sm rounded-md bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md border animate-in fade-in-0 zoom-in-95"
            sideOffset={5}
          >
            <div className="space-y-1">
              <p className="font-medium text-sm">{citation.file_name}</p>
              <p className="text-xs text-muted-foreground">{citation.location}</p>
              <p className="text-xs italic line-clamp-3">"{citation.excerpt}"</p>
            </div>
            <Tooltip.Arrow className="fill-popover" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
