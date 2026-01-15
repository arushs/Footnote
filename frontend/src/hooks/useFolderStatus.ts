import { useState, useEffect, useCallback, useRef } from 'react'
import type { FolderStatus, Folder } from '../types'

interface UseFolderStatusOptions {
  folderId: string
  pollInterval?: number
  onIndexingComplete?: () => void
  enabled?: boolean
}

export function useFolderStatus({ folderId, pollInterval = 2000, onIndexingComplete, enabled = true }: UseFolderStatusOptions) {
  const [folder, setFolder] = useState<Folder | null>(null)
  const [status, setStatus] = useState<FolderStatus | null>(null)
  const wasIndexingRef = useRef(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchFolder = useCallback(async () => {
    try {
      const response = await fetch(`/api/folders/${folderId}`)
      if (!response.ok) throw new Error('Folder not found')
      const data: Folder = await response.json()
      setFolder(data)
      return data
    } catch (err) {
      setError((err as Error).message)
      return null
    }
  }, [folderId])

  const fetchStatus = useCallback(async () => {
    try {
      const response = await fetch(`/api/folders/${folderId}/status`)
      if (!response.ok) throw new Error('Failed to fetch status')
      const data: FolderStatus = await response.json()
      setStatus(data)
      return data
    } catch (err) {
      setError((err as Error).message)
      return null
    }
  }, [folderId])

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false)
      return
    }

    let mounted = true
    let intervalId: ReturnType<typeof setInterval> | null = null

    const initialize = async () => {
      setIsLoading(true)
      const folderData = await fetchFolder()
      if (!mounted) return

      if (folderData) {
        const statusData = await fetchStatus()
        if (!mounted) return

        setIsLoading(false)

        // Poll if indexing is in progress
        if (statusData && (statusData.status === 'pending' || statusData.status === 'indexing')) {
          intervalId = setInterval(async () => {
            const newStatus = await fetchStatus()
            if (!mounted) return

            // Stop polling when done
            if (newStatus && (newStatus.status === 'ready' || newStatus.status === 'failed')) {
              if (intervalId) {
                clearInterval(intervalId)
                intervalId = null
              }
            }
          }, pollInterval)
        }
      } else {
        setIsLoading(false)
      }
    }

    initialize()

    return () => {
      mounted = false
      if (intervalId) clearInterval(intervalId)
    }
  }, [folderId, fetchFolder, fetchStatus, pollInterval, enabled])

  const isIndexing = status?.status === 'pending' || status?.status === 'indexing'
  const isReady = status?.status === 'ready'
  const isFailed = status?.status === 'failed'
  const progress = status && status.files_total > 0
    ? Math.round((status.files_indexed / status.files_total) * 100)
    : 0

  // Detect transition from indexing to ready
  useEffect(() => {
    if (wasIndexingRef.current && isReady && onIndexingComplete) {
      onIndexingComplete()
    }
    wasIndexingRef.current = isIndexing
  }, [isIndexing, isReady, onIndexingComplete])

  return {
    folder,
    status,
    isLoading,
    error,
    isIndexing,
    isReady,
    isFailed,
    progress,
    refetch: fetchStatus,
  }
}
