import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useChat } from './useChat'
import type { Citation } from '../types'

// Mock fetch
const mockFetch = vi.fn()
global.fetch = mockFetch

// Helper to create a mock SSE response
function createMockSSEResponse(chunks: Array<{ token?: string; done?: boolean; citations?: Record<string, Citation>; searched_files?: string[]; conversation_id?: string; agent_status?: { phase: string; iteration: number; tool?: string } }>) {
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

    it('should call fetch with correct parameters for non-agent mode', async () => {
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
            agent_mode: false,
            max_iterations: 10,
          }),
        })
      )
    })

    it('should call fetch with agent_mode true when enabled', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1', agentMode: true, maxIterations: 8 }))

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
            agent_mode: true,
            max_iterations: 8,
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

  describe('Agent Status', () => {
    it('should set agentStatus to undefined when agentMode is false', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { token: 'Response' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1', agentMode: false }))

      await act(async () => {
        await result.current.sendMessage('Hello')
      })

      // agentStatus should remain undefined when not in agent mode
      expect(result.current.agentStatus).toBeUndefined()
    })

    it('should parse agent_status SSE events', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { agent_status: { phase: 'searching', iteration: 1 } },
        { agent_status: { phase: 'reading_file', iteration: 2, tool: 'get_file' } },
        { token: 'Found the information.' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1', agentMode: true, maxIterations: 10 }))

      // Track agentStatus changes during streaming
      const statusHistory: (AgentStatus | undefined)[] = []

      await act(async () => {
        const sendPromise = result.current.sendMessage('Find data')

        // Wait a bit and capture statuses during streaming
        await new Promise(resolve => setTimeout(resolve, 10))
        statusHistory.push(result.current.agentStatus)

        await sendPromise
      })

      // After completion, agentStatus should be cleared
      expect(result.current.agentStatus).toBeUndefined()
    })

    it('should update agentStatus phase to generating when tokens start', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { agent_status: { phase: 'searching', iteration: 1 } },
        { token: 'Here is the answer.' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1', agentMode: true }))

      await act(async () => {
        await result.current.sendMessage('Question')
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      // After completion, agentStatus should be cleared
      expect(result.current.agentStatus).toBeUndefined()
      // But the message should contain the response
      expect(result.current.messages).toHaveLength(2)
      expect(result.current.messages[1].content).toBe('Here is the answer.')
    })

    it('should clear agentStatus when conversation completes', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { agent_status: { phase: 'searching', iteration: 1 } },
        { agent_status: { phase: 'processing', iteration: 2 } },
        { token: 'Response' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1', agentMode: true }))

      await act(async () => {
        await result.current.sendMessage('Test')
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      // agentStatus should be undefined after completion
      expect(result.current.agentStatus).toBeUndefined()
    })

    it('should not set agentStatus when agentMode is false', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { token: 'Response' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1', agentMode: false }))

      await act(async () => {
        await result.current.sendMessage('Hello')
      })

      await waitFor(() => {
        expect(result.current.isLoading).toBe(false)
      })

      expect(result.current.agentStatus).toBeUndefined()
    })

    it('should pass maxIterations to the API request', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { token: 'Response' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1', agentMode: true, maxIterations: 15 }))

      await act(async () => {
        await result.current.sendMessage('Hello')
      })

      // Verify max_iterations was passed in the request
      expect(mockFetch).toHaveBeenCalledWith(
        '/api/folders/folder-1/chat',
        expect.objectContaining({
          body: JSON.stringify({
            message: 'Hello',
            agent_mode: true,
            max_iterations: 15,
          }),
        })
      )
    })

    it('should handle agent_status SSE events with tool information', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { agent_status: { phase: 'reading_file', iteration: 2, tool: 'get_file' } },
        { token: 'Response' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result } = renderHook(() => useChat({ folderId: 'folder-1', agentMode: true }))

      await act(async () => {
        await result.current.sendMessage('Hello')
      })

      // After completion, agentStatus should be cleared but message should be present
      expect(result.current.agentStatus).toBeUndefined()
      expect(result.current.messages).toHaveLength(2)
      expect(result.current.messages[1].content).toBe('Response')
    })
  })

  describe('Folder change behavior', () => {
    it('should reset state when folderId changes', async () => {
      mockFetch.mockResolvedValueOnce(createMockSSEResponse([
        { token: 'Response' },
        { done: true, citations: {}, searched_files: [], conversation_id: 'conv-1' },
      ]))

      const { result, rerender } = renderHook(
        ({ folderId }) => useChat({ folderId }),
        { initialProps: { folderId: 'folder-1' } }
      )

      // Send a message in folder-1
      await act(async () => {
        await result.current.sendMessage('Hello')
      })

      await waitFor(() => {
        expect(result.current.messages).toHaveLength(2)
      })

      // Change folder
      rerender({ folderId: 'folder-2' })

      // State should be reset
      expect(result.current.messages).toEqual([])
      expect(result.current.currentConversationId).toBeNull()
      expect(result.current.streamingContent).toBe('')
      expect(result.current.agentStatus).toBeUndefined()
    })
  })
})
