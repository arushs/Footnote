import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import _userEvent from '@testing-library/user-event'
import { BrowserRouter } from 'react-router-dom'
import { AppShell } from '../layout/AppShell'
import { Header, UserMenu } from '../layout/Header'
import { AuthProvider } from '../../contexts/AuthContext'

// Wrapper for components that need routing
const RouterWrapper = ({ children }: { children: React.ReactNode }) => (
  <BrowserRouter>{children}</BrowserRouter>
)

// Wrapper for components that need auth context
const AuthWrapper = ({ children }: { children: React.ReactNode }) => (
  <BrowserRouter>
    <AuthProvider>{children}</AuthProvider>
  </BrowserRouter>
)

describe('AppShell', () => {
  it('should render children', () => {
    render(
      <AppShell>
        <div data-testid="child">Test Content</div>
      </AppShell>
    )

    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.getByText('Test Content')).toBeInTheDocument()
  })

  it('should have min-h-screen and flex-col classes', () => {
    render(
      <AppShell>
        <div>Content</div>
      </AppShell>
    )

    const container = screen.getByText('Content').parentElement
    expect(container).toHaveClass('min-h-screen', 'flex', 'flex-col')
  })

  it('should accept custom className', () => {
    render(
      <AppShell className="custom-class">
        <div>Content</div>
      </AppShell>
    )

    const container = screen.getByText('Content').parentElement
    expect(container).toHaveClass('custom-class')
  })

  describe('AppShell.Header', () => {
    it('should render header with border', () => {
      render(
        <AppShell>
          <AppShell.Header>Header Content</AppShell.Header>
        </AppShell>
      )

      const header = screen.getByRole('banner')
      expect(header).toBeInTheDocument()
      expect(header).toHaveTextContent('Header Content')
      expect(header).toHaveClass('border-b', 'h-14')
    })
  })

  describe('AppShell.Sidebar', () => {
    it('should render left sidebar with border-r by default', () => {
      render(
        <AppShell>
          <AppShell.Sidebar>Sidebar Content</AppShell.Sidebar>
        </AppShell>
      )

      const sidebar = screen.getByText('Sidebar Content').closest('aside')
      expect(sidebar).toBeInTheDocument()
      expect(sidebar).toHaveClass('border-r')
    })

    it('should render right sidebar with border-l', () => {
      render(
        <AppShell>
          <AppShell.Sidebar position="right">Right Sidebar</AppShell.Sidebar>
        </AppShell>
      )

      const sidebar = screen.getByText('Right Sidebar').closest('aside')
      expect(sidebar).toHaveClass('border-l')
    })

    it('should apply width classes based on width prop', () => {
      const { rerender } = render(
        <AppShell>
          <AppShell.Sidebar width="sm">Small Sidebar</AppShell.Sidebar>
        </AppShell>
      )

      expect(screen.getByText('Small Sidebar').closest('aside')).toHaveClass('w-56')

      rerender(
        <AppShell>
          <AppShell.Sidebar width="lg">Large Sidebar</AppShell.Sidebar>
        </AppShell>
      )

      expect(screen.getByText('Large Sidebar').closest('aside')).toHaveClass('w-72')
    })

    it('should collapse when collapsible and collapsed', () => {
      render(
        <AppShell>
          <AppShell.Sidebar collapsible collapsed>
            Collapsed Sidebar
          </AppShell.Sidebar>
        </AppShell>
      )

      const sidebar = screen.getByText('Collapsed Sidebar').closest('aside')
      expect(sidebar).toHaveClass('w-0', 'overflow-hidden')
    })
  })

  describe('AppShell.Main', () => {
    it('should render main content area', () => {
      render(
        <AppShell>
          <AppShell.Main>Main Content</AppShell.Main>
        </AppShell>
      )

      const main = screen.getByRole('main')
      expect(main).toBeInTheDocument()
      expect(main).toHaveTextContent('Main Content')
      expect(main).toHaveClass('flex-1', 'min-w-0')
    })
  })
})

describe('Header', () => {
  it('should render header with children', () => {
    render(
      <RouterWrapper>
        <Header>
          <div>Header Content</div>
        </Header>
      </RouterWrapper>
    )

    const header = screen.getByRole('banner')
    expect(header).toBeInTheDocument()
    expect(header).toHaveClass('h-14', 'border-b')
  })

  describe('Header.Brand', () => {
    it('should render default title', () => {
      render(
        <RouterWrapper>
          <Header>
            <Header.Brand />
          </Header>
        </RouterWrapper>
      )

      expect(screen.getByText('Talk to a Folder')).toBeInTheDocument()
    })

    it('should render custom title', () => {
      render(
        <RouterWrapper>
          <Header>
            <Header.Brand title="Custom Title" />
          </Header>
        </RouterWrapper>
      )

      expect(screen.getByText('Custom Title')).toBeInTheDocument()
    })

    it('should render back button when backTo is provided', () => {
      render(
        <RouterWrapper>
          <Header>
            <Header.Brand backTo="/folders" backLabel="Folders" />
          </Header>
        </RouterWrapper>
      )

      expect(screen.getByText('Folders')).toBeInTheDocument()
    })

    it('should render default back label', () => {
      render(
        <RouterWrapper>
          <Header>
            <Header.Brand backTo="/folders" />
          </Header>
        </RouterWrapper>
      )

      expect(screen.getByText('Back')).toBeInTheDocument()
    })

    it('should link to folders page', () => {
      render(
        <RouterWrapper>
          <Header>
            <Header.Brand title="Test" />
          </Header>
        </RouterWrapper>
      )

      const link = screen.getByRole('link')
      expect(link).toHaveAttribute('href', '/folders')
    })
  })

  describe('Header.Actions', () => {
    it('should render children in actions area', () => {
      render(
        <RouterWrapper>
          <Header>
            <Header.Actions>
              <button>Action Button</button>
            </Header.Actions>
          </Header>
        </RouterWrapper>
      )

      expect(screen.getByRole('button', { name: 'Action Button' })).toBeInTheDocument()
    })
  })
})

describe('UserMenu', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should not render when user is not logged in', () => {
    render(
      <AuthWrapper>
        <UserMenu />
      </AuthWrapper>
    )

    // UserMenu returns null when no user
    expect(screen.queryByText('Sign out')).not.toBeInTheDocument()
  })
})
