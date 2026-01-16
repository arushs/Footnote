import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, act } from '@testing-library/react'
import { AuthProvider, useAuth } from './AuthContext'

// Mock fetch
const mockFetch = vi.fn()
global.fetch = mockFetch

// Test component to access auth context
function TestComponent() {
  const { user, loading, logout } = useAuth()
  return (
    <div>
      <span data-testid="loading">{loading.toString()}</span>
      <span data-testid="user">{user ? user.email : 'null'}</span>
      <button onClick={logout}>Logout</button>
    </div>
  )
}

describe('AuthContext', () => {
  const mockUser = {
    id: 'user-1',
    email: 'test@example.com',
    google_id: 'google-123',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('useAuth hook', () => {
    it('should throw error when used outside AuthProvider', () => {
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      expect(() => {
        render(<TestComponent />)
      }).toThrow('useAuth must be used within an AuthProvider')

      consoleSpy.mockRestore()
    })
  })

  describe('AuthProvider', () => {
    it('should start with loading true', async () => {
      mockFetch.mockImplementation(() => new Promise(() => {})) // Never resolves

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      expect(screen.getByTestId('loading')).toHaveTextContent('true')
    })

    it('should set user after successful auth check', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: async () => mockUser,
      })

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false')
      })

      expect(screen.getByTestId('user')).toHaveTextContent('test@example.com')
      expect(mockFetch).toHaveBeenCalledWith('/api/auth/me', {
        credentials: 'include',
      })
    })

    it('should set user to null when not authenticated', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 401,
      })

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false')
      })

      expect(screen.getByTestId('user')).toHaveTextContent('null')
    })

    it('should set user to null on network error', async () => {
      mockFetch.mockRejectedValueOnce(new Error('Network error'))

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('loading')).toHaveTextContent('false')
      })

      expect(screen.getByTestId('user')).toHaveTextContent('null')
    })
  })

  describe('logout', () => {
    it('should call logout endpoint and clear user', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockUser,
        })
        .mockResolvedValueOnce({
          ok: true,
        })

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('user')).toHaveTextContent('test@example.com')
      })

      await act(async () => {
        screen.getByText('Logout').click()
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
      })
      expect(screen.getByTestId('user')).toHaveTextContent('null')
    })

    it('should clear user even if logout request fails', async () => {
      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: async () => mockUser,
        })
        .mockRejectedValueOnce(new Error('Network error'))

      render(
        <AuthProvider>
          <TestComponent />
        </AuthProvider>
      )

      await waitFor(() => {
        expect(screen.getByTestId('user')).toHaveTextContent('test@example.com')
      })

      await act(async () => {
        screen.getByText('Logout').click()
      })

      expect(screen.getByTestId('user')).toHaveTextContent('null')
    })
  })
})
