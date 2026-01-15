import { Link, useNavigate } from 'react-router-dom'
import { LogOut, ChevronLeft, FolderOpen } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { cn } from '../../lib/utils'

interface HeaderProps {
  children?: React.ReactNode
  className?: string
}

interface HeaderBrandProps {
  title?: string
  backTo?: string
  backLabel?: string
}

interface HeaderActionsProps {
  children?: React.ReactNode
}

/**
 * Header provides a consistent top navigation bar.
 * Use Header.Brand for logo/title and Header.Actions for user actions.
 *
 * @example
 * ```tsx
 * <Header>
 *   <Header.Brand title="Talk to a Folder" />
 *   <Header.Actions>
 *     <UserMenu />
 *   </Header.Actions>
 * </Header>
 * ```
 */
export function Header({ children, className }: HeaderProps) {
  return (
    <header
      className={cn(
        'h-14 border-b border-border bg-background shrink-0',
        'flex items-center justify-between px-4 gap-4',
        className
      )}
    >
      {children}
    </header>
  )
}

function HeaderBrand({ title = 'Talk to a Folder', backTo, backLabel }: HeaderBrandProps) {
  const navigate = useNavigate()

  return (
    <div className="flex items-center gap-3">
      {backTo && (
        <button
          onClick={() => navigate(backTo)}
          className={cn(
            'flex items-center gap-1 text-sm text-muted-foreground',
            'hover:text-foreground transition-colors',
            '-ml-1 px-2 py-1 rounded-md hover:bg-muted'
          )}
        >
          <ChevronLeft className="h-4 w-4" />
          {backLabel || 'Back'}
        </button>
      )}
      <Link to="/chat" className="flex items-center gap-2">
        <div className="h-8 w-8 rounded-lg bg-primary flex items-center justify-center">
          <FolderOpen className="h-4 w-4 text-primary-foreground" />
        </div>
        <span className="font-semibold text-foreground">{title}</span>
      </Link>
    </div>
  )
}

function HeaderActions({ children }: HeaderActionsProps) {
  return <div className="flex items-center gap-2">{children}</div>
}

/**
 * UserMenu displays the current user email and logout button.
 * Use within Header.Actions.
 */
export function UserMenu() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = async () => {
    await logout()
    navigate('/')
  }

  if (!user) return null

  return (
    <div className="flex items-center gap-3">
      <span className="text-sm text-muted-foreground hidden sm:inline">
        {user.email}
      </span>
      <button
        onClick={handleLogout}
        className={cn(
          'flex items-center gap-2 px-3 py-1.5 rounded-md text-sm',
          'text-muted-foreground hover:text-foreground',
          'hover:bg-muted transition-colors'
        )}
        title="Sign out"
      >
        <LogOut className="h-4 w-4" />
        <span className="hidden sm:inline">Sign out</span>
      </button>
    </div>
  )
}

// Attach sub-components
Header.Brand = HeaderBrand
Header.Actions = HeaderActions
