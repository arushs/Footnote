import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { FolderDropdown } from './FolderDropdown'
import type { Folder } from '../../types'

// Mock useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useParams: () => ({ folderId: 'folder-1' }),
  }
})

// Mock useGooglePicker
vi.mock('../../hooks', () => ({
  useGooglePicker: vi.fn(() => ({
    isLoaded: true,
    isConfigured: true,
    openPicker: vi.fn(),
  })),
}))

// Mock fetch
const mockFetch = vi.fn()
global.fetch = mockFetch

const renderFolderDropdown = (currentFolderName?: string) => {
  return render(
    <MemoryRouter initialEntries={['/chat/folder-1']}>
      <Routes>
        <Route path="/chat/:folderId" element={<FolderDropdown currentFolderName={currentFolderName} />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('FolderDropdown', () => {
  const mockFolders: Folder[] = [
    {
      id: 'folder-1',
      google_folder_id: 'google-1',
      folder_name: 'My Documents',
      index_status: 'ready',
      files_total: 10,
      files_indexed: 10,
      last_synced_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(), // 2 hours ago
    },
    {
      id: 'folder-2',
      google_folder_id: 'google-2',
      folder_name: 'Work Files',
      index_status: 'ready',
      files_total: 5,
      files_indexed: 5,
      last_synced_at: new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString(), // 1 day ago
    },
    {
      id: 'folder-3',
      google_folder_id: 'google-3',
      folder_name: 'Indexing Folder',
      index_status: 'indexing',
      files_total: 8,
      files_indexed: 3,
      last_synced_at: null,
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    mockFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ folders: mockFolders }),
    })
  })

  describe('Dropdown trigger', () => {
    it('should display current folder name', async () => {
      renderFolderDropdown('My Documents')

      expect(screen.getByText('My Documents')).toBeInTheDocument()
    })

    it('should display "Select folder" when no folder name provided', async () => {
      renderFolderDropdown()

      expect(screen.getByText('Select folder')).toBeInTheDocument()
    })

    it('should have switch folder aria label', async () => {
      renderFolderDropdown('My Documents')

      expect(screen.getByRole('button', { name: /switch folder/i })).toBeInTheDocument()
    })
  })

  describe('Dropdown content', () => {
    it('should fetch folders on mount', async () => {
      renderFolderDropdown('My Documents')

      await waitFor(() => {
        expect(mockFetch).toHaveBeenCalledWith('/api/folders', {
          credentials: 'include',
        })
      })
    })

    it('should show folders in dropdown when opened', async () => {
      const user = userEvent.setup()
      renderFolderDropdown('My Documents')

      const trigger = screen.getByRole('button', { name: /switch folder/i })
      await user.click(trigger)

      await waitFor(() => {
        expect(screen.getByText('Work Files')).toBeInTheDocument()
      })
    })

    it('should show last synced time for folders', async () => {
      const user = userEvent.setup()
      renderFolderDropdown('My Documents')

      const trigger = screen.getByRole('button', { name: /switch folder/i })
      await user.click(trigger)

      await waitFor(() => {
        expect(screen.getByText('2h ago')).toBeInTheDocument()
        expect(screen.getByText('1d ago')).toBeInTheDocument()
      })
    })

    it('should show indexing folders as disabled', async () => {
      const user = userEvent.setup()
      renderFolderDropdown('My Documents')

      const trigger = screen.getByRole('button', { name: /switch folder/i })
      await user.click(trigger)

      await waitFor(() => {
        expect(screen.getByText('Indexing Folder')).toBeInTheDocument()
        expect(screen.getByText('Indexing...')).toBeInTheDocument()
      })
    })

    it('should show "Add new folder" option', async () => {
      const user = userEvent.setup()
      renderFolderDropdown('My Documents')

      const trigger = screen.getByRole('button', { name: /switch folder/i })
      await user.click(trigger)

      await waitFor(() => {
        expect(screen.getByText('Add new folder')).toBeInTheDocument()
      })
    })
  })

  describe('Folder selection', () => {
    it('should navigate to selected folder', async () => {
      const user = userEvent.setup()
      renderFolderDropdown('My Documents')

      const trigger = screen.getByRole('button', { name: /switch folder/i })
      await user.click(trigger)

      await waitFor(() => {
        expect(screen.getByText('Work Files')).toBeInTheDocument()
      })

      const workFilesOption = screen.getByText('Work Files')
      await user.click(workFilesOption)

      expect(mockNavigate).toHaveBeenCalledWith('/chat/folder-2')
    })
  })

  describe('Last synced formatting', () => {
    it('should show "Never synced" for null last_synced_at', async () => {
      mockFetch.mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({
          folders: [
            {
              id: 'folder-1',
              google_folder_id: 'google-1',
              folder_name: 'Unsynced Folder',
              index_status: 'ready',
              files_total: 5,
              files_indexed: 5,
              last_synced_at: null,
            },
          ],
        }),
      })

      const user = userEvent.setup()
      renderFolderDropdown('Unsynced Folder')

      const trigger = screen.getByRole('button', { name: /switch folder/i })
      await user.click(trigger)

      await waitFor(() => {
        expect(screen.getByText('Never synced')).toBeInTheDocument()
      })
    })
  })

  describe('Loading state', () => {
    it('should show loading spinner while fetching folders', async () => {
      mockFetch.mockImplementation(() => new Promise(() => {})) // Keep pending

      const user = userEvent.setup()
      renderFolderDropdown('My Documents')

      const trigger = screen.getByRole('button', { name: /switch folder/i })
      await user.click(trigger)

      // The loading spinner should be visible in the dropdown
      await waitFor(() => {
        expect(document.querySelector('.animate-spin')).toBeInTheDocument()
      })
    })
  })

  describe('Error handling', () => {
    it('should handle fetch error gracefully', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'))

      renderFolderDropdown('My Documents')

      // Should not crash, component should still render
      await waitFor(() => {
        expect(screen.getByText('My Documents')).toBeInTheDocument()
      })
    })
  })
})
