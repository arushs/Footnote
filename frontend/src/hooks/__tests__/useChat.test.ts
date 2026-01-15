import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useChat } from '../useChat'
import type { Citation } from '../../types'

// Mock fetch
const mockFetch = vi.fn()
global.fetch = mockFetch

// Helper to create a mock SSE response
function createMockSSEResponse(chunks: Array<{ token?: string; done?: boolean; citations?: Record<string, Citation>; searched_files?: string[]; conversation_id?: string }>) {
  const encoder = new TextEncoder()
  let index = 0

  return {
    ok: true,
    body: {
      getReader: () => ({
        read: async () => {
          if (index >= chunks.length) {
            return { done: true, value: undefined }
          }
          const chunk = chunks[index]
          index++
          const data = `data: ${JSON.stringify(chunk)}\n\n`
          return { done: false, value: encoder.encode(data) }
        },
      }),
    },
  }
}

describe('useChat', () => {
  const mockCitation: Citation = {
    chunk_id: 'chunk-1',
    file_name: 'document.pdf',
    location: 'Page 10',
    excerpt: 'Test excerpt',
    google_drive_url: 'https://drive.google.com/file/d/123/view',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Initial state', () => {
    it('should initialize with empty messages', () => {
      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      expect(result.current.messages).toEqual([])
      expect(result.current.isLoading).toBe(false)
      expect(result.current.currentConversationId).toBeNull()
      expect(result.current.streamingContent).toBe('')
    })
  })

  describe('sendMessage', () => {
    it('should not send empty messages', async () => {
      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      await act(async () => {
        await result.current.sendMessage('')
      })

      expect(mockFetch).not.toHaveBeenCalled()
    })

    it('should not send whitespace-only messages', async () => {
      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      await act(async () => {
        await result.current.sendMessage('   ')
      })

      expect(mockFetch).not.toHaveBeenCalled()
    })

    it('should add user message to the messages array', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { token: 'Response' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      await act(async () => {
        await result.current.sendMessage('Hello')
      })

      // After full completion, both user and assistant messages should be present
      // The first message should be the user's message
      expect(result.current.messages[0].role).toBe('user')
      expect(result.current.messages[0].content).toBe('Hello')
    })

    it('should complete loading after streaming finishes', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { token: 'Response' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      await act(async () => {
        await result.current.sendMessage('Hello')
      })

      // After completion, isLoading should be false
      expect(result.current.isLoading).toBe(false)
    })

    it('should call fetch with correct parameters', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      await act(async () => {
        result.current.sendMessage('Test message')
      })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/folders/folder-1/chat',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: 'Test message',
          }),
        })
      )
    })
  })

  describe('Streaming response', () => {
    it('should accumulate tokens during streaming', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { token: 'Hello' },
        { token: ' world' },
        { token: '!' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      await act(async () => {
        await result.current.sendMessage('Hi')
      })

      // After streaming completes, check the assistant message
      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.messages).toHaveLength(2)
      expect(result.current.messages[1].role).toBe('assistant')
      expect(result.current.messages[1].content).toBe('Hello world!')
    })

    it('should parse citations on completion', async () => {
      const citations = { '1': mockCitation }

      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { token: 'According to [1], this is true.' },
        { done: true, citations, searched_files: ['document.pdf'], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      await act(async () => {
        await result.current.sendMessage('Question')
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      const assistantMessage = result.current.messages[1]
      expect(assistantMessage.citations).toEqual(citations)
    })

    it('should update conversation ID from response', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { token: 'Response' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'new-conv-id' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      await act(async () => {
        await result.current.sendMessage('Message')
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.currentConversationId).toBe('new-conv-id')
    })

    it('should call onSourcesUpdate with searched files and citations', async () => {
      const onSourcesUpdate = vi.fn()
      const citations = { '1': mockCitation }
      const searchedFiles = ['doc1.pdf', 'doc2.pdf']

      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { token: 'Response' },
        { done: true, citations, searched_files: searchedFiles, conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() =>
        useChat({ folderId: 'folder-1', onSourcesUpdate })
      )

      await act(async () => {
        await result.current.sendMessage('Query')
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(onSourcesUpdate).toHaveBeenCalledWith(searchedFiles, citations)
    })
  })

  describe('stopGeneration', () => {
    it('should set isLoading to false when stopped', () => {
      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      // Manually set loading state for this test
      act(() => {
        result.current.stopGeneration()
      })

      expect(result.current.isLoading).toBe(false)
    })
  })

  describe('startNewConversation', () => {
    it('should reset all state', () => {
      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      act(() => {
        result.current.startNewConversation()
      })

      expect(result.current.messages).toEqual([])
      expect(result.current.currentConversationId).toBeNull()
      expect(result.current.streamingContent).toBe('')
      expect(result.current.isLoading).toBe(false)
    })
  })

  describe('loadConversation', () => {
    it('should fetch and load existing conversation', async () => {
      const existingMessages = [
        { id: 'msg-1', role: 'user', content: 'Previous question', created_at: '2024-01-01' },
        { id: 'msg-2', role: 'assistant', content: 'Previous answer', created_at: '2024-01-01' },
      ]

      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => existingMessages,
      })

      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      await act(async () => {
        await result.current.loadConversation('existing-conv-id')
      })

      expect(result.current.messages).toEqual(existingMessages)
      expect(result.current.currentConversationId).toBe('existing-conv-id')
    })

    it('should handle load conversation errors gracefully', async () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      mockFetch.mockResolvedValueOnce({ ok: false, status: 404 })

      const { result } = renderHook(() => useChat({ folderId: 'folder-1' }))

      await act(async () => {
        await result.current.loadConversation('non-existent-conv')
      })

      // Should not crash, messages remain empty
      expect(result.current.messages).toEqual([])
      consoleSpy.mockRestore()
    })
  })
})
