import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor, act } from '@testing-library/react'
import { useGooglePicker } from '../useGooglePicker'

// Mock environment variables
vi.mock('../../lib/env', () => ({}))

describe('useGooglePicker', () => {
  const originalEnv = import.meta.env

  beforeEach(() => {
    vi.clearAllMocks()
    // Reset window.gapi and window.google
    delete (window as any).gapi
    delete (window as any).google
  })

  afterEach(() => {
    // Restore env
    import.meta.env = originalEnv
  })

  describe('Configuration check', () => {
    it('should set error when API key is missing', async () => {
      // Mock missing env vars by not setting up the mocks
      vi.stubEnv('VITE_GOOGLE_API_KEY', '')
      vi.stubEnv('VITE_GOOGLE_CLIENT_ID', '')

      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      const { result } = renderHook(() => useGooglePicker())

      await waitFor(() => {
        expect(result.current.isConfigured).toBe(false)
      })

      consoleSpy.mockRestore()
    })
  })

  describe('Script loading', () => {
    it('should start with isLoaded false', () => {
      vi.stubEnv('VITE_GOOGLE_API_KEY', 'test-api-key')
      vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'test-client-id')

      const { result } = renderHook(() => useGooglePicker())

      expect(result.current.isLoaded).toBe(false)
    })
  })

  describe('openPicker', () => {
    it('should throw error if APIs not loaded', async () => {
      vi.stubEnv('VITE_GOOGLE_API_KEY', 'test-api-key')
      vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'test-client-id')

      const { result } = renderHook(() => useGooglePicker())

      await expect(result.current.openPicker()).rejects.toThrow('Google APIs not loaded')
    })
  })

  describe('With mocked Google APIs', () => {
    const mockPickerResult = {
      id: 'folder-123',
      name: 'My Folder',
      mimeType: 'application/vnd.google-apps.folder',
    }

    beforeEach(() => {
      vi.stubEnv('VITE_GOOGLE_API_KEY', 'test-api-key')
      vi.stubEnv('VITE_GOOGLE_CLIENT_ID', 'test-client-id')

      // Setup mock Google APIs
      const mockSetVisible = vi.fn()
      const mockBuild = vi.fn(() => ({ setVisible: mockSetVisible }))
      const mockCallback = vi.fn()

      ;(window as any).gapi = {
        load: vi.fn((api: string, callback: () => void) => {
          callback()
        }),
      }

      const mockDocsView = {
        setIncludeFolders: vi.fn().mockReturnThis(),
        setSelectFolderEnabled: vi.fn().mockReturnThis(),
      }

      ;(window as any).google = {
        picker: {
          PickerBuilder: vi.fn().mockImplementation(function() {
            return {
              addView: vi.fn().mockReturnThis(),
              setOAuthToken: vi.fn().mockReturnThis(),
              setDeveloperKey: vi.fn().mockReturnThis(),
              setTitle: vi.fn().mockReturnThis(),
              setCallback: vi.fn(function(cb: any) {
                mockCallback.mockImplementation(cb)
                return this
              }),
              build: mockBuild,
            }
          }),
          ViewId: {
            FOLDERS: 'FOLDERS',
            DOCS: 'DOCS',
          },
          DocsView: vi.fn(() => mockDocsView),
          Feature: {
            MULTISELECT_ENABLED: 'MULTISELECT_ENABLED',
            NAV_HIDDEN: 'NAV_HIDDEN',
          },
          Action: {
            PICKED: 'PICKED',
            CANCEL: 'CANCEL',
          },
        },
        accounts: {
          oauth2: {
            initTokenClient: vi.fn(({ callback }) => ({
              requestAccessToken: () => {
                callback({ access_token: 'test-token' })
              },
            })),
          },
        },
      }
    })

    it('should set isLoaded to true after loading APIs', async () => {
      const { result } = renderHook(() => useGooglePicker())

      await waitFor(() => {
        expect(result.current.isLoaded).toBe(true)
      })
    })

    it('should set isConfigured to true with valid env vars', async () => {
      const { result } = renderHook(() => useGooglePicker())

      await waitFor(() => {
        expect(result.current.isConfigured).toBe(true)
      })
    })

    it('should clear error after successful load', async () => {
      const { result } = renderHook(() => useGooglePicker())

      await waitFor(() => {
        expect(result.current.error).toBeNull()
      })
    })
  })
})
