import ReactMarkdown from 'react-markdown'

interface StreamingMessageProps {
  content: string
}

export function StreamingMessage({ content }: StreamingMessageProps) {
  return (
    <div className="px-4 py-3">
      <div className="prose prose-sm max-w-none dark:prose-invert">
        <ReactMarkdown>{content}</ReactMarkdown>
        <span className="inline-block w-2 h-4 ml-1 bg-foreground animate-pulse" />
      </div>
    </div>
  )
}
