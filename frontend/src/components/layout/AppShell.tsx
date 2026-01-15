import { cn } from '../../lib/utils'

interface AppShellProps {
  children: React.ReactNode
  className?: string
}

interface AppShellHeaderProps {
  children: React.ReactNode
  className?: string
}

interface AppShellSidebarProps {
  children: React.ReactNode
  className?: string
  position?: 'left' | 'right'
  width?: 'sm' | 'md' | 'lg'
  collapsible?: boolean
  collapsed?: boolean
}

interface AppShellMainProps {
  children: React.ReactNode
  className?: string
}

const widthClasses = {
  sm: 'w-56',
  md: 'w-64',
  lg: 'w-72',
}

/**
 * AppShell provides the main application layout structure.
 * Compose with AppShell.Header, AppShell.Sidebar, and AppShell.Main.
 *
 * @example
 * ```tsx
 * <AppShell>
 *   <AppShell.Header>Header content</AppShell.Header>
 *   <div className="flex flex-1">
 *     <AppShell.Sidebar>Left sidebar</AppShell.Sidebar>
 *     <AppShell.Main>Main content</AppShell.Main>
 *     <AppShell.Sidebar position="right">Right sidebar</AppShell.Sidebar>
 *   </div>
 * </AppShell>
 * ```
 */
export function AppShell({ children, className }: AppShellProps) {
  return (
    <div
      className={cn(
        'min-h-screen flex flex-col bg-background',
        className
      )}
    >
      {children}
    </div>
  )
}

function AppShellHeader({ children, className }: AppShellHeaderProps) {
  return (
    <header
      className={cn(
        'h-14 border-b border-border bg-background shrink-0',
        'flex items-center px-4',
        className
      )}
    >
      {children}
    </header>
  )
}

function AppShellSidebar({
  children,
  className,
  position = 'left',
  width = 'md',
  collapsible = false,
  collapsed = false,
}: AppShellSidebarProps) {
  const borderClass = position === 'left' ? 'border-r' : 'border-l'

  return (
    <aside
      className={cn(
        'flex flex-col bg-background shrink-0 transition-all duration-200',
        borderClass,
        'border-border',
        collapsible && collapsed ? 'w-0 overflow-hidden' : widthClasses[width],
        className
      )}
    >
      {children}
    </aside>
  )
}

function AppShellMain({ children, className }: AppShellMainProps) {
  return (
    <main
      className={cn(
        'flex-1 flex flex-col min-w-0 overflow-hidden',
        className
      )}
    >
      {children}
    </main>
  )
}

// Attach sub-components
AppShell.Header = AppShellHeader
AppShell.Sidebar = AppShellSidebar
AppShell.Main = AppShellMain
