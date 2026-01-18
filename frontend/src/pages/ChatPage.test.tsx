import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ChatPage } from './ChatPage'
import { AuthProvider } from '../contexts/AuthContext'

// Mock the hooks
vi.mock('../../hooks', () => ({
  useChat: vi.fn(() => ({
    messages: [],
    isLoading: false,
    streamingContent: '',
    currentConversationId: null,
    sendMessage: vi.fn(),
    stopGeneration: vi.fn(),
    loadConversation: vi.fn(),
    startNewConversation: vi.fn(),
  })),
  useConversations: vi.fn(() => ({
    conversations: [],
    isLoading: false,
    refetch: vi.fn(),
  })),
  useFolderStatus: vi.fn(() => ({
    folder: null,
    status: null,
    isIndexing: false,
  })),
  useGooglePicker: vi.fn(() => ({
    isLoaded: true,
    isConfigured: true,
    openPicker: vi.fn(),
  })),
}))

// Mock fetch
const mockFetch = vi.fn()
global.fetch = mockFetch

const renderChatPage = (route = '/chat') => {
  return render(
    <MemoryRouter initialEntries={[route]}>
      <AuthProvider>
        <Routes>
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/chat/:folderId" element={<ChatPage />} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('ChatPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ folders: [] }),
    })
  })

  describe('EmptyState (no folderId)', () => {
    it('should render the empty state when no folder is selected', async () => {
      renderChatPage('/chat')

      await waitFor(() => {
        expect(screen.getByText('How can I help you?')).toBeInTheDocument()
      })
      expect(screen.getByText('Select a folder to start chatting with your documents.')).toBeInTheDocument()
    })

    it('should show loading spinner while fetching folders', () => {
      // Keep the fetch pending
      mockFetch.mockImplementation(() => new Promise(() => {}))

      renderChatPage('/chat')

      // Should show loading state (the Loader2 spinner)
      expect(screen.getByRole('heading', { name: 'How can I help you?' })).toBeInTheDocument()
    })

    it('should fetch folders on mount', async () => {
      renderChatPage('/chat')

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith('/api/folders', {
          credentials: 'include',
        })
      })
    })

    it('should show folder dropdown when folders exist', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          folders: [
            { id: '1', folder_name: 'My Documents', index_status: 'ready' },
            { id: '2', folder_name: 'Work Files', index_status: 'ready' },
          ],
        }),
      })

      renderChatPage('/chat')

      await waitFor(() => {
        expect(screen.getByText('Select a folder...')).toBeInTheDocument()
      })
    })

    it('should show Add folder button', async () => {
      renderChatPage('/chat')

      await waitFor(() => {
        expect(screen.getByText('Add a Google Drive folder')).toBeInTheDocument()
      })
    })

    it('should open folder dropdown when clicked', async () => {
      const user = userEvent.setup()

      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          folders: [
            { id: '1', folder_name: 'My Documents', index_status: 'ready' },
          ],
        }),
      })

      renderChatPage('/chat')

      await waitFor(() => {
        expect(screen.getByText('Select a folder...')).toBeInTheDocument()
      })

      await user.click(screen.getByText('Select a folder...'))

      await waitFor(() => {
        expect(screen.getByText('My Documents')).toBeInTheDocument()
      })
    })

    it('should show indexing folders as disabled', async () => {
      const user = userEvent.setup()

      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          folders: [
            { id: '1', folder_name: 'Ready Folder', index_status: 'ready' },
            { id: '2', folder_name: 'Indexing Folder', index_status: 'indexing' },
          ],
        }),
      })

      renderChatPage('/chat')

      await waitFor(() => {
        expect(screen.getByText('Select a folder...')).toBeInTheDocument()
      })

      await user.click(screen.getByText('Select a folder...'))

      await waitFor(() => {
        expect(screen.getByText('Ready Folder')).toBeInTheDocument()
        expect(screen.getByText('Indexing...')).toBeInTheDocument()
        expect(screen.getByText('Indexing Folder')).toBeInTheDocument()
      })
    })
  })
})
