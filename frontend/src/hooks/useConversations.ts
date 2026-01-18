import { useState, useEffect, useCallback } from 'react'
import { apiUrl } from '../config/api'
import type { Conversation } from '../types'

interface UseConversationsOptions {
  folderId: string
  enabled?: boolean
}

export function useConversations({ folderId, enabled = true }: UseConversationsOptions) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchConversations = useCallback(async () => {
    if (!enabled) return

    try {
      setIsLoading(true)
      const response = await fetch(apiUrl(`/api/folders/${folderId}/conversations`), {
        credentials: 'include',
      })
      if (!response.ok) throw new Error('Failed to fetch conversations')
      const data: Conversation[] = await response.json()
      setConversations(data)
      setError(null)
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setIsLoading(false)
    }
  }, [folderId, enabled])

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false)
      return
    }
    fetchConversations()
  }, [fetchConversations, enabled])

  return {
    conversations,
    isLoading,
    error,
    refetch: fetchConversations,
  }
}
