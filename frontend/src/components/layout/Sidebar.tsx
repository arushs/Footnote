import * as ScrollArea from '@radix-ui/react-scroll-area'
import { cn } from '../../lib/utils'

interface SidebarProps {
  children: React.ReactNode
  className?: string
  position?: 'left' | 'right'
}

interface SidebarHeaderProps {
  children: React.ReactNode
  className?: string
}

interface SidebarContentProps {
  children: React.ReactNode
  className?: string
  scrollable?: boolean
}

interface SidebarFooterProps {
  children: React.ReactNode
  className?: string
}

/**
 * Sidebar provides a consistent sidebar layout structure.
 * Use Sidebar.Header, Sidebar.Content, and Sidebar.Footer for sections.
 *
 * @example
 * ```tsx
 * <Sidebar position="left">
 *   <Sidebar.Header>
 *     <h2>Chat History</h2>
 *   </Sidebar.Header>
 *   <Sidebar.Content scrollable>
 *     {conversations.map(...)}
 *   </Sidebar.Content>
 * </Sidebar>
 * ```
 */
export function Sidebar({ children, className, position = 'left' }: SidebarProps) {
  const borderClass = position === 'left' ? 'border-r' : 'border-l'

  return (
    <aside
      className={cn(
        'flex flex-col bg-background',
        borderClass,
        'border-border',
        className
      )}
    >
      {children}
    </aside>
  )
}

function SidebarHeader({ children, className }: SidebarHeaderProps) {
  return (
    <div
      className={cn(
        'p-4 border-b border-border shrink-0',
        className
      )}
    >
      {children}
    </div>
  )
}

function SidebarContent({ children, className, scrollable = false }: SidebarContentProps) {
  if (scrollable) {
    return (
      <ScrollArea.Root className="flex-1 overflow-hidden">
        <ScrollArea.Viewport className={cn('h-full w-full', className)}>
          {children}
        </ScrollArea.Viewport>
        <ScrollArea.Scrollbar
          className="flex touch-none select-none bg-muted/50 p-0.5 transition-colors hover:bg-muted data-[orientation=vertical]:w-2.5"
          orientation="vertical"
        >
          <ScrollArea.Thumb className="relative flex-1 rounded-full bg-border" />
        </ScrollArea.Scrollbar>
      </ScrollArea.Root>
    )
  }

  return (
    <div className={cn('flex-1 overflow-auto', className)}>
      {children}
    </div>
  )
}

function SidebarFooter({ children, className }: SidebarFooterProps) {
  return (
    <div
      className={cn(
        'p-4 border-t border-border shrink-0',
        className
      )}
    >
      {children}
    </div>
  )
}

// Attach sub-components
Sidebar.Header = SidebarHeader
Sidebar.Content = SidebarContent
Sidebar.Footer = SidebarFooter
