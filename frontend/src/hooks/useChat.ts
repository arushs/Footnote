import { useState, useCallback, useRef } from 'react'
import type { Message, Citation, ChatState } from '../types'
import { addToast } from '../components/ui/toast'

interface UseChatOptions {
  folderId: string
  onSourcesUpdate?: (searchedFiles: string[], citations: Record<string, Citation>) => void
  enabled?: boolean
}

export function useChat({ folderId, onSourcesUpdate, enabled = true }: UseChatOptions) {
  const [state, setState] = useState<ChatState>({
    messages: [],
    isLoading: false,
    currentConversationId: null,
    streamingContent: '',
    streamingCitations: {},
  })

  const abortControllerRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (content: string) => {
    if (!enabled || !content.trim() || state.isLoading) return

    // Add user message
    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      created_at: new Date().toISOString(),
    }

    setState(prev => ({
      ...prev,
      messages: [...prev.messages, userMessage],
      isLoading: true,
      streamingContent: '',
      streamingCitations: {},
    }))

    // Abort any existing request
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
    abortControllerRef.current = new AbortController()

    try {
      const response = await fetch(`/api/folders/${folderId}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          message: content,
          conversation_id: state.currentConversationId,
        }),
        signal: abortControllerRef.current.signal,
      })

      if (!response.ok) {
        throw new Error('Failed to send message')
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('No response body')

      const decoder = new TextDecoder()
      let accumulatedContent = ''
      let accumulatedCitations: Record<string, Citation> = {}
      let searchedFiles: string[] = []
      let conversationId = state.currentConversationId

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue

          try {
            const data = JSON.parse(line.slice(6))

            if (data.token) {
              accumulatedContent += data.token
              setState(prev => ({
                ...prev,
                streamingContent: accumulatedContent,
              }))
            }

            if (data.done) {
              if (data.citations) {
                accumulatedCitations = data.citations
                setState(prev => ({
                  ...prev,
                  streamingCitations: data.citations,
                }))
              }
              if (data.searched_files) {
                searchedFiles = data.searched_files
              }
              if (data.conversation_id) {
                conversationId = data.conversation_id
              }
            }
          } catch {
            // Skip malformed JSON
          }
        }
      }

      // Create final assistant message
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: accumulatedContent,
        citations: accumulatedCitations,
        created_at: new Date().toISOString(),
      }

      setState(prev => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
        isLoading: false,
        streamingContent: '',
        streamingCitations: {},
        currentConversationId: conversationId,
      }))

      // Update sources panel
      if (onSourcesUpdate) {
        onSourcesUpdate(searchedFiles, accumulatedCitations)
      }

    } catch (error) {
      if ((error as Error).name === 'AbortError') return

      console.error('Chat error:', error)
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message'
      addToast(errorMessage, 'error')
      setState(prev => ({
        ...prev,
        isLoading: false,
        streamingContent: '',
      }))
    }
  }, [folderId, state.isLoading, state.currentConversationId, onSourcesUpdate, enabled])

  const stopGeneration = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      setState(prev => ({
        ...prev,
        isLoading: false,
      }))
    }
  }, [])

  const loadConversation = useCallback(async (conversationId: string) => {
    try {
      const response = await fetch(`/api/conversations/${conversationId}/messages`, {
        credentials: 'include',
      })
      if (!response.ok) throw new Error('Failed to load conversation')

      const messages: Message[] = await response.json()
      setState(prev => ({
        ...prev,
        messages,
        currentConversationId: conversationId,
      }))
    } catch (error) {
      console.error('Failed to load conversation:', error)
      addToast('Failed to load conversation', 'error')
    }
  }, [])

  const startNewConversation = useCallback(() => {
    setState({
      messages: [],
      isLoading: false,
      currentConversationId: null,
      streamingContent: '',
      streamingCitations: {},
    })
  }, [])

  return {
    ...state,
    sendMessage,
    stopGeneration,
    loadConversation,
    startNewConversation,
  }
}
