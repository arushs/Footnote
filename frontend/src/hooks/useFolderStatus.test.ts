import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useFolderStatus } from '../useFolderStatus'
import type { Folder, FolderStatus } from '../../types'

// Mock fetch
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('useFolderStatus', () => {
  const mockFolder: Folder = {
    id: 'folder-1',
    google_folder_id: 'google-123',
    name: 'Test Folder',
    created_at: '2024-01-15T10:00:00Z',
  }

  const mockStatusReady: FolderStatus = {
    status: 'ready',
    files_total: 10,
    files_indexed: 10,
  }

  const mockStatusIndexing: FolderStatus = {
    status: 'indexing',
    files_total: 10,
    files_indexed: 5,
  }

  const mockStatusPending: FolderStatus = {
    status: 'pending',
    files_total: 0,
    files_indexed: 0,
  }

  const mockStatusFailed: FolderStatus = {
    status: 'failed',
    files_total: 10,
    files_indexed: 3,
  }

  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('Initial state', () => {
    it('should start with loading true', () => {
      mockFetch.mockImplementation(() => new Promise(() => {})) // Never resolves
      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      expect(result.current.isLoading).toBe(true)
      expect(result.current.folder).toBeNull()
      expect(result.current.status).toBeNull()
    })

    it('should not fetch when disabled', async () => {
      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1', enabled: false })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(mockFetch).not.toHaveBeenCalled()
    })
  })

  describe('Fetching folder and status', () => {
    it('should fetch folder and status on mount', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusReady,
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/folders/folder-1')
      expect(mockFetch).toHaveBeenCalledWith('/api/folders/folder-1/status')
      expect(result.current.folder).toEqual(mockFolder)
      expect(result.current.status).toEqual(mockStatusReady)
    })
  })

  describe('Status flags', () => {
    it('should correctly identify ready status', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusReady,
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.isReady).toBe(true)
      expect(result.current.isIndexing).toBe(false)
      expect(result.current.isFailed).toBe(false)
    })

    it('should correctly identify indexing status', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusIndexing,
        })
        // Mock polling response
        .mockResolvedValue({
          ok: true,
          json: async () => mockStatusIndexing,
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.isReady).toBe(false)
      expect(result.current.isIndexing).toBe(true)
      expect(result.current.isFailed).toBe(false)
    })

    it('should correctly identify pending status as indexing', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusPending,
        })
        .mockResolvedValue({
          ok: true,
          json: async () => mockStatusPending,
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.isIndexing).toBe(true)
    })

    it('should correctly identify failed status', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusFailed,
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.isReady).toBe(false)
      expect(result.current.isIndexing).toBe(false)
      expect(result.current.isFailed).toBe(true)
    })
  })

  describe('Progress calculation', () => {
    it('should calculate progress correctly', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusIndexing, // 5 of 10 = 50%
        })
        .mockResolvedValue({
          ok: true,
          json: async () => mockStatusIndexing,
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.progress).toBe(50)
    })

    it('should return 0 progress when no files', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusPending, // 0 of 0
        })
        .mockResolvedValue({
          ok: true,
          json: async () => mockStatusPending,
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.progress).toBe(0)
    })

    it('should return 100 progress when complete', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusReady, // 10 of 10
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.progress).toBe(100)
    })
  })

  describe('Polling behavior', () => {
    it('should poll when indexing', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusIndexing,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusIndexing,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusReady,
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1', pollInterval: 1000 })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.isIndexing).toBe(true)

      // Advance timer to trigger polling
      await act(async () => {
        vi.advanceTimersByTime(1000)
      })

      // Advance again to get ready status
      await act(async () => {
        vi.advanceTimersByTime(1000)
      })

      await waitFor(() => {
        expect(result.current.isReady).toBe(true)
      })
    })

    it('should not poll when already ready', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusReady,
        })

      renderHook(() =>
        useFolderStatus({ folderId: 'folder-1', pollInterval: 1000 })
      )

      await act(async () => {
        vi.advanceTimersByTime(5000)
      })

      // Should only have called for initial fetch (folder + status)
      expect(mockFetch).toHaveBeenCalledTimes(2)
    })
  })

  describe('onIndexingComplete callback', () => {
    it('should call onIndexingComplete when transitioning from indexing to ready', async () => {
      const onIndexingComplete = vi.fn()

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusIndexing,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusReady,
        })

      const { result } = renderHook(() =>
        useFolderStatus({
          folderId: 'folder-1',
          pollInterval: 1000,
          onIndexingComplete,
        })
      )

      await waitFor(() => {
        expect(result.current.isIndexing).toBe(true)
      })

      // Trigger poll
      await act(async () => {
        vi.advanceTimersByTime(1000)
      })

      await waitFor(() => {
        expect(result.current.isReady).toBe(true)
      })

      expect(onIndexingComplete).toHaveBeenCalledTimes(1)
    })

    it('should not call onIndexingComplete if already ready on mount', async () => {
      const onIndexingComplete = vi.fn()

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusReady,
        })

      const { result } = renderHook(() =>
        useFolderStatus({
          folderId: 'folder-1',
          onIndexingComplete,
        })
      )

      await waitFor(() => {
        expect(result.current.isReady).toBe(true)
      })

      expect(onIndexingComplete).not.toHaveBeenCalled()
    })
  })

  describe('Error handling', () => {
    it('should handle folder not found', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
      })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe('Folder not found')
      expect(result.current.folder).toBeNull()
    })

    it('should handle status fetch error', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 500,
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.error).toBe('Failed to fetch status')
      })
    })
  })

  describe('Refetch', () => {
    it('should refetch status when refetch is called', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockFolder,
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockStatusIndexing,
        })
        .mockResolvedValue({
          ok: true,
          json: async () => mockStatusReady,
        })

      const { result } = renderHook(() =>
        useFolderStatus({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isIndexing).toBe(true)
      })

      await act(async () => {
        await result.current.refetch()
      })

      await waitFor(() => {
        expect(result.current.isReady).toBe(true)
      })
    })
  })
})
