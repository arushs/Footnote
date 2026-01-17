import { Bot } from 'lucide-react'
import ReactMarkdown from 'react-markdown'

interface StreamingMessageProps {
  content: string
}

export function StreamingMessage({ content }: StreamingMessageProps) {
  return (
    <div className="group flex gap-3 px-4 py-4 bg-background">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-secondary">
        <Bot className="h-4 w-4" />
      </div>

      <div className="flex-1 space-y-2 overflow-hidden">
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown>{content}</ReactMarkdown>
          <span className="inline-block w-2 h-4 ml-1 bg-foreground animate-pulse" />
        </div>
      </div>
    </div>
  )
}
