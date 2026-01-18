import { useState, useEffect, useCallback, useRef } from 'react'
import { addToast } from '../components/ui/toast'
import { apiUrl } from '../config/api'
import type { FolderStatus, Folder } from '../types'

interface UseFolderStatusOptions {
  folderId: string
  pollInterval?: number
  onIndexingComplete?: () => void
  onSyncComplete?: () => void
  enabled?: boolean
}

export function useFolderStatus({ folderId, pollInterval = 2000, onIndexingComplete, onSyncComplete, enabled = true }: UseFolderStatusOptions) {
  const [folder, setFolder] = useState<Folder | null>(null)
  const [status, setStatus] = useState<FolderStatus | null>(null)
  const wasIndexingRef = useRef(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchFolder = useCallback(async () => {
    try {
      const response = await fetch(apiUrl(`/api/folders/${folderId}`), {
        credentials: 'include',
      })
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
      const response = await fetch(apiUrl(`/api/folders/${folderId}/status`), {
        credentials: 'include',
      })
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

  // Trigger background sync on folder switch (only for ready folders)
  useEffect(() => {
    if (!enabled || !folderId || !isReady) return

    const controller = new AbortController()

    fetch(apiUrl(`/api/folders/${folderId}/sync`), {
      method: 'POST',
      credentials: 'include',
      signal: controller.signal,
    })
      .then((res) => res.json())
      .then((result) => {
        if (result.synced) {
          const changes = (result.added ?? 0) + (result.modified ?? 0)
          if (changes > 0) {
            addToast(`Found ${changes} new file${changes > 1 ? 's' : ''}`, 'info')
          }
          // Refetch folder data to update last_synced_at
          fetchFolder()
          // Notify parent to refresh folder list
          onSyncComplete?.()
        }
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          console.error('Background sync failed:', err)
        }
      })

    return () => controller.abort()
  }, [enabled, folderId, isReady, fetchFolder, onSyncComplete])

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
