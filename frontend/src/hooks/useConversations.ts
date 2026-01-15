import { useState, useEffect, useCallback } from 'react'
import type { Conversation } from '../types'

interface UseConversationsOptions {
  folderId: string
}

export function useConversations({ folderId }: UseConversationsOptions) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchConversations = useCallback(async () => {
    try {
      setIsLoading(true)
      const response = await fetch(`/api/folders/${folderId}/conversations`)
      if (!response.ok) throw new Error('Failed to fetch conversations')
      const data: Conversation[] = await response.json()
      setConversations(data)
      setError(null)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setIsLoading(false)
    }
  }, [folderId])

  useEffect(() => {
    fetchConversations()
  }, [fetchConversations])

  return {
    conversations,
    isLoading,
    error,
    refetch: fetchConversations,
  }
}
