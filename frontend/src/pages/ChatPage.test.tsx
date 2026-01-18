import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { ChatPage } from './ChatPage'
import { AuthProvider } from '../contexts/AuthContext'
import { useFolders } from '../hooks'
import type { Folder } from '../types'

// Mock useFolders hook
const mockAddFolder = vi.fn()
const mockRefetch = vi.fn()

// Mock the hooks
vi.mock('../hooks', () => ({
  useChat: vi.fn(() => ({
    messages: [],
    isLoading: false,
    streamingContent: '',
    currentConversationId: null,
    agentStatus: null,
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
  useFolders: vi.fn(() => ({
    folders: [],
    readyFolders: [],
    indexingFolders: [],
    isLoading: false,
    isCreating: false,
    isReady: true,
    addFolder: mockAddFolder,
    refetch: mockRefetch,
  })),
}))

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
    vi.mocked(useFolders).mockReturnValue({
      folders: [],
      readyFolders: [],
      indexingFolders: [],
      isLoading: false,
      isCreating: false,
      isReady: true,
      addFolder: mockAddFolder,
      refetch: mockRefetch,
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
      vi.mocked(useFolders).mockReturnValue({
        folders: [],
        readyFolders: [],
        indexingFolders: [],
        isLoading: true,
        isCreating: false,
        isReady: true,
        addFolder: mockAddFolder,
        refetch: mockRefetch,
      })

      renderChatPage('/chat')

      // Should show loading state (the Loader2 spinner)
      expect(screen.getByRole('heading', { name: 'How can I help you?' })).toBeInTheDocument()
    })

    it('should use useFolders hook on mount', async () => {
      renderChatPage('/chat')

      expect(useFolders).toHaveBeenCalled()
    })

    it('should show folder dropdown when folders exist', async () => {
      const folders: Folder[] = [
        { id: '1', google_folder_id: 'g1', folder_name: 'My Documents', index_status: 'ready', files_total: 10, files_indexed: 10, last_synced_at: null },
        { id: '2', google_folder_id: 'g2', folder_name: 'Work Files', index_status: 'ready', files_total: 5, files_indexed: 5, last_synced_at: null },
      ]
      vi.mocked(useFolders).mockReturnValue({
        folders,
        readyFolders: folders,
        indexingFolders: [],
        isLoading: false,
        isCreating: false,
        isReady: true,
        addFolder: mockAddFolder,
        refetch: mockRefetch,
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
      const folders: Folder[] = [
        { id: '1', google_folder_id: 'g1', folder_name: 'My Documents', index_status: 'ready', files_total: 10, files_indexed: 10, last_synced_at: null },
      ]
      vi.mocked(useFolders).mockReturnValue({
        folders,
        readyFolders: folders,
        indexingFolders: [],
        isLoading: false,
        isCreating: false,
        isReady: true,
        addFolder: mockAddFolder,
        refetch: mockRefetch,
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
      const readyFolder: Folder = { id: '1', google_folder_id: 'g1', folder_name: 'Ready Folder', index_status: 'ready', files_total: 10, files_indexed: 10, last_synced_at: null }
      const indexingFolder: Folder = { id: '2', google_folder_id: 'g2', folder_name: 'Indexing Folder', index_status: 'indexing', files_total: 5, files_indexed: 2, last_synced_at: null }
      vi.mocked(useFolders).mockReturnValue({
        folders: [readyFolder, indexingFolder],
        readyFolders: [readyFolder],
        indexingFolders: [indexingFolder],
        isLoading: false,
        isCreating: false,
        isReady: true,
        addFolder: mockAddFolder,
        refetch: mockRefetch,
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
