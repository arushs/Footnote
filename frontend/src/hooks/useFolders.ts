import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useGooglePicker } from './useGooglePicker'
import { addToast } from '../components/ui/toast'
import { apiUrl } from '../config/api'
import type { Folder } from '../types'

interface UseFoldersOptions {
  /** Whether to fetch folders on mount */
  enabled?: boolean
}

interface UseFoldersReturn {
  folders: Folder[]
  readyFolders: Folder[]
  indexingFolders: Folder[]
  isLoading: boolean
  isCreating: boolean
  isReady: boolean
  addFolder: () => Promise<void>
  refetch: () => Promise<void>
}

export function useFolders(options: UseFoldersOptions = {}): UseFoldersReturn {
  const { enabled = true } = options
  const navigate = useNavigate()
  const { isLoaded, isConfigured, openPicker } = useGooglePicker()
  const [folders, setFolders] = useState<Folder[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [isCreating, setIsCreating] = useState(false)

  const fetchFolders = useCallback(async (signal?: AbortSignal) => {
    try {
      setIsLoading(true)
      const response = await fetch(apiUrl('/api/folders'), {
        credentials: 'include',
        signal,
      })
      if (!response.ok) throw new Error('Failed to fetch folders')
      const data = await response.json()
      setFolders(data.folders)
    } catch (err) {
      if (err instanceof Error && err.name !== 'AbortError') {
        addToast('Failed to load folders', 'error')
      }
    } finally {
      setIsLoading(false)
    }
  }, [])

  useEffect(() => {
    if (!enabled) {
      setIsLoading(false)
      return
    }

    const controller = new AbortController()
    fetchFolders(controller.signal)

    return () => controller.abort()
  }, [enabled, fetchFolders])

  // Poll when there are indexing folders
  useEffect(() => {
    if (!enabled) return

    const hasIndexingFolders = folders.some(
      (f) => f.index_status === 'indexing' || f.index_status === 'pending'
    )

    if (!hasIndexingFolders) return

    const intervalId = setInterval(() => {
      fetchFolders()
    }, 3000)

    return () => clearInterval(intervalId)
  }, [enabled, folders, fetchFolders])

  const addFolder = useCallback(async () => {
    if (!isConfigured || !isLoaded) {
      addToast('Google Drive integration not ready', 'error')
      return
    }

    try {
      const result = await openPicker()
      if (!result) return

      setIsCreating(true)
      const response = await fetch(apiUrl('/api/folders'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          google_folder_id: result.id,
          folder_name: result.name,
        }),
      })

      if (response.ok) {
        const newFolder = await response.json()
        // Update local state immediately
        setFolders((prev) => [...prev, newFolder])
        addToast(`Added folder "${result.name}"`, 'success')
        navigate(`/chat/${newFolder.id}`)
      } else {
        const error = await response.json().catch(() => ({}))
        addToast(error.detail || 'Failed to add folder', 'error')
      }
    } catch {
      addToast('Failed to add folder', 'error')
    } finally {
      setIsCreating(false)
    }
  }, [isConfigured, isLoaded, openPicker, navigate])

  const refetch = useCallback(() => fetchFolders(), [fetchFolders])

  const readyFolders = folders.filter((f) => f.index_status === 'ready')
  const indexingFolders = folders.filter((f) => f.index_status === 'indexing')

  return {
    folders,
    readyFolders,
    indexingFolders,
    isLoading,
    isCreating,
    isReady: isConfigured && isLoaded,
    addFolder,
    refetch,
  }
}
