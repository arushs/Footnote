import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useConversations } from '../useConversations'
import type { Conversation } from '../../types'

// Mock fetch
const mockFetch = vi.fn()
global.fetch = mockFetch

describe('useConversations', () => {
  const mockConversations: Conversation[] = [
    {
      id: 'conv-1',
      folder_id: 'folder-1',
      preview: 'First conversation',
      created_at: '2024-01-15T10:00:00Z',
    },
    {
      id: 'conv-2',
      folder_id: 'folder-1',
      preview: 'Second conversation',
      created_at: '2024-01-14T10:00:00Z',
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Initial state', () => {
    it('should start with loading true', () => {
      mockFetch.mockImplementation(() => new Promise(() => {})) // Never resolves
      const { result } = renderHook(() =>
        useConversations({ folderId: 'folder-1' })
      )

      expect(result.current.isLoading).toBe(true)
      expect(result.current.conversations).toEqual([])
      expect(result.current.error).toBeNull()
    })

    it('should not fetch when disabled', async () => {
      const { result } = renderHook(() =>
        useConversations({ folderId: 'folder-1', enabled: false })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(mockFetch).not.toHaveBeenCalled()
      expect(result.current.conversations).toEqual([])
    })
  })

  describe('Fetching conversations', () => {
    it('should fetch conversations on mount', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockConversations,
      })

      const { result } = renderHook(() =>
        useConversations({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/folders/folder-1/conversations')
      expect(result.current.conversations).toEqual(mockConversations)
      expect(result.current.error).toBeNull()
    })

    it('should fetch with correct folder ID', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      })

      renderHook(() => useConversations({ folderId: 'my-folder-123' }))

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith('/api/folders/my-folder-123/conversations')
      })
    })
  })

  describe('Error handling', () => {
    it('should handle fetch failure', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
      })

      const { result } = renderHook(() =>
        useConversations({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe('Failed to fetch conversations')
      expect(result.current.conversations).toEqual([])
    })

    it('should handle network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      const { result } = renderHook(() =>
        useConversations({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.error).toBe('Network error')
      expect(result.current.conversations).toEqual([])
    })
  })

  describe('Refetch', () => {
    it('should refetch conversations when refetch is called', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => [mockConversations[0]],
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockConversations,
        })

      const { result } = renderHook(() =>
        useConversations({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.conversations).toHaveLength(1)

      await act(async () => {
        await result.current.refetch()
      })

      expect(result.current.conversations).toHaveLength(2)
      expect(mockFetch).toHaveBeenCalledTimes(2)
    })

    it('should clear previous error on successful refetch', async () => {
      mockFetch
        .mockResolvedValueOnce({ ok: false })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockConversations,
        })

      const { result } = renderHook(() =>
        useConversations({ folderId: 'folder-1' })
      )

      await waitFor(() => {
        expect(result.current.error).toBe('Failed to fetch conversations')
      })

      await act(async () => {
        await result.current.refetch()
      })

      expect(result.current.error).toBeNull()
      expect(result.current.conversations).toEqual(mockConversations)
    })
  })

  describe('Folder ID changes', () => {
    it('should refetch when folder ID changes', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => [mockConversations[0]],
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => [mockConversations[1]],
        })

      const { result, rerender } = renderHook(
        ({ folderId }) => useConversations({ folderId }),
        { initialProps: { folderId: 'folder-1' } }
      )

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.conversations[0].id).toBe('conv-1')

      rerender({ folderId: 'folder-2' })

      await waitFor(() => {
        expect(result.current.conversations[0].id).toBe('conv-2')
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/folders/folder-2/conversations')
    })
  })
})
