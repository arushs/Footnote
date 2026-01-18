import {
  useState,
  ReactNode,
  Children,
  isValidElement,
  cloneElement,
} from 'react'
import { Copy, Check, ChevronRight } from 'lucide-react'
import * as Tooltip from '@radix-ui/react-tooltip'
import ReactMarkdown from 'react-markdown'
import type { Message, Citation } from '../../types'
import { cn } from '../../lib/utils'

export interface ChatMessageProps {
  message: Message
  onCitationClick?: (citation: Citation) => void
  isSourcesOpen?: boolean
  onToggleSources?: () => void
}

export function ChatMessage({
  message,
  onCitationClick,
  isSourcesOpen,
  onToggleSources,
}: ChatMessageProps) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'
  const hasCitations =
    message.citations && Object.keys(message.citations).length > 0
  const citationCount = hasCitations
    ? Object.keys(message.citations!).length
    : 0

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // Process text to replace citation markers with clickable elements
  const processCitations = (text: string): ReactNode[] => {
    if (!message.citations || Object.keys(message.citations).length === 0) {
      return [text]
    }

    const citationPattern = /\[(\d+)\]/g
    const parts: ReactNode[] = []
    let lastIndex = 0
    let match

    while ((match = citationPattern.exec(text)) !== null) {
      if (match.index > lastIndex) {
        parts.push(text.slice(lastIndex, match.index))
      }

      const citationKey = match[1]
      const citation = message.citations[citationKey]

      if (citation) {
        parts.push(
          <CitationMarker
            key={`citation-${match.index}-${citationKey}`}
            citation={citation}
            onClick={() => onCitationClick?.(citation)}
          />
        )
      } else {
        parts.push(match[0])
      }

      lastIndex = match.index + match[0].length
    }

    if (lastIndex < text.length) {
      parts.push(text.slice(lastIndex))
    }

    return parts
  }

  // Recursively process children to inject citation markers
  const processChildren = (children: ReactNode): ReactNode => {
    return Children.map(children, (child) => {
      if (typeof child === 'string') {
        const processed = processCitations(child)
        return processed.length === 1 && typeof processed[0] === 'string'
          ? processed[0]
          : <>{processed}</>
      }
      if (isValidElement(child) && child.props.children) {
        return cloneElement(child, {
          ...child.props,
          children: processChildren(child.props.children),
        })
      }
      return child
    })
  }

  const renderContent = () => {
    return (
      <ReactMarkdown
        components={{
          // Process citations in all text-containing elements
          p: ({ children }) => <p>{processChildren(children)}</p>,
          li: ({ children }) => <li>{processChildren(children)}</li>,
          td: ({ children }) => <td>{processChildren(children)}</td>,
          th: ({ children }) => <th>{processChildren(children)}</th>,
          // Ensure code blocks don't get citation processing
          code: ({ className, children, ...props }) => (
            <code className={className} {...props}>
              {children}
            </code>
          ),
        }}
      >
        {message.content}
      </ReactMarkdown>
    )
  }

  // User messages: right-aligned bubble
  if (isUser) {
    return (
      <article className="flex justify-end px-4 py-3" aria-label="Your message">
        <div className="max-w-[80%] rounded-3xl bg-muted px-4 py-2.5">
          <p className="text-sm whitespace-pre-wrap">{message.content}</p>
        </div>
      </article>
    )
  }

  // Assistant messages: left-aligned plain text with copy button below
  return (
    <article className="group px-4 py-3" aria-label="Assistant response">
      <div className="space-y-2">
        <div className="prose prose-sm max-w-none dark:prose-invert">
          {renderContent()}
        </div>

        <div className="flex items-center gap-2 pt-1">
          {hasCitations && onToggleSources && (
            <SourcesPill
              count={citationCount}
              isOpen={isSourcesOpen ?? false}
              onClick={onToggleSources}
            />
          )}
          <button
            onClick={handleCopy}
            className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity h-7 px-2 flex items-center gap-1.5 rounded-md hover:bg-muted text-xs text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label={copied ? 'Copied to clipboard' : 'Copy response'}
            title="Copy response"
          >
            {copied ? (
              <>
                <Check
                  className="h-3.5 w-3.5 text-green-500"
                  aria-hidden="true"
                />
                <span className="text-green-500">Copied</span>
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>
    </article>
  )
}

interface CitationMarkerProps {
  citation: Citation
  onClick: () => void
}

function CitationMarker({ citation, onClick }: CitationMarkerProps) {
  const displayName =
    citation.file_name.length > 20
      ? citation.file_name.slice(0, 17) + '...'
      : citation.file_name

  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button
            onClick={onClick}
            className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-primary/10 text-primary rounded-full hover:bg-primary/20 transition-colors mx-0.5 focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label={`Source: ${citation.file_name}`}
          >
            {displayName}
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="z-50 max-w-sm rounded-md bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md border animate-in fade-in-0 zoom-in-95"
            sideOffset={5}
          >
            <div className="space-y-1">
              <p className="font-medium text-sm">{citation.file_name}</p>
              <p className="text-xs text-muted-foreground">
                {citation.location}
              </p>
              <p className="text-xs italic line-clamp-3">
                "{citation.excerpt}"
              </p>
            </div>
            <Tooltip.Arrow className="fill-popover" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}

interface SourcesPillProps {
  count: number
  isOpen: boolean
  onClick: () => void
}

function SourcesPill({ count, isOpen, onClick }: SourcesPillProps) {
  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium bg-muted hover:bg-muted/80 rounded-full transition-colors"
      aria-expanded={isOpen}
      aria-label={`${isOpen ? 'Hide' : 'Show'} ${count} sources`}
    >
      <span>Sources ({count})</span>
      <ChevronRight
        className={cn('w-4 h-4 transition-transform', isOpen && 'rotate-180')}
      />
    </button>
  )
}
