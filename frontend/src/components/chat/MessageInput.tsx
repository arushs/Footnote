import { useState, useRef, useEffect } from 'react'
import { Send, Square } from 'lucide-react'
import { cn } from '../../lib/utils'

export interface MessageInputProps {
  onSend: (message: string) => void
  onStop?: () => void
  isLoading?: boolean
  disabled?: boolean
  placeholder?: string
}

export function MessageInput({
  onSend,
  onStop,
  isLoading = false,
  disabled = false,
  placeholder = 'Ask about your files...',
}: MessageInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    }
  }, [value])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (value.trim() && !isLoading && !disabled) {
      onSend(value.trim())
      setValue('')
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="border-t border-border p-4">
      <div className="relative flex items-end gap-2">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className={cn(
            'flex-1 resize-none rounded-lg border border-input bg-background px-4 py-3 text-sm',
            'placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring',
            'disabled:cursor-not-allowed disabled:opacity-50',
            'max-h-[200px] min-h-[48px]'
          )}
        />
        {isLoading ? (
          <button
            type="button"
            onClick={onStop}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg bg-destructive text-destructive-foreground hover:bg-destructive/90 transition-colors"
            title="Stop generation"
          >
            <Square className="h-4 w-4" />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!value.trim() || disabled}
            className={cn(
              'flex h-12 w-12 shrink-0 items-center justify-center rounded-lg transition-colors',
              value.trim() && !disabled
                ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                : 'bg-muted text-muted-foreground cursor-not-allowed'
            )}
            title="Send message"
          >
            <Send className="h-4 w-4" />
          </button>
        )}
      </div>
      <p className="mt-2 text-xs text-muted-foreground text-center">
        Press Enter to send, Shift+Enter for new line
      </p>
    </form>
  )
}
