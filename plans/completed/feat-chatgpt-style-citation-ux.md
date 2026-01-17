# feat: Improved Citation UX with Collapsible Sources Panel

## Overview

Improve the citation UX with two simple changes:
1. Show source names in inline badges instead of numbers
2. Add a "Sources" pill button that toggles the existing right sidebar

No new dependencies. Reuse existing `SourcesPanel` component.

## Problem Statement

**Current:** Inline citations show as `[1]`, `[2]` which don't convey source identity at a glance.

**Target:** Inline badges show truncated source names (e.g., `[Project Spec]`, `[Budget.xlsx]`) and sidebar is collapsible via a pill button.

## Proposed Solution

### 1. Inline Citation Badges (Show Source Names)

Update `CitationMarker` to display truncated file name instead of number:

**Before:** `The timeline was updated [1] and budget approved [2].`

**After:** `The timeline was updated [Project Spec] and budget approved [Budget.xlsx].`

### 2. Sources Pill Button (Toggle Sidebar)

Add a pill button below the chat that shows source count and toggles the right sidebar:

```
+------------------+
| Sources (5)  [>] |
+------------------+
```

- Hidden when 0 citations
- Click opens/closes the existing `SourcesPanel` sliding in from right
- Sidebar hidden by default, shown on pill click

## Technical Approach

### No New Dependencies

Reuse existing:
- `SourcesPanel.tsx` (as-is)
- Radix UI Tooltip (already installed)
- CSS transitions for slide animation

### Files to Modify

| File | Change |
|------|--------|
| `frontend/src/components/chat/ChatMessage.tsx` | Update `CitationMarker` to show file name |
| `frontend/src/pages/ChatPage.tsx` | Add sidebar toggle state + Sources pill button |

### Component Architecture

```
ChatPage.tsx
├── ChatHistorySidebar (left, unchanged)
├── Main Content
│   ├── MessageList
│   │   └── ChatMessage (inline name badges)
│   ├── SourcesPill (NEW - toggles sidebar)
│   └── MessageInput
└── SourcesPanel (right, now collapsible)
```

## Acceptance Criteria

- [ ] Inline citations display source name (truncated to 20 chars max)
- [ ] Existing hover tooltip behavior preserved
- [ ] Clicking badge opens Google Drive URL (unchanged)
- [ ] "Sources (N)" pill appears when citations exist
- [ ] Clicking pill toggles right sidebar open/closed
- [ ] Sidebar hidden by default, slides in from right
- [ ] 0 citations: pill hidden

## Implementation

### 1. Update CitationMarker in ChatMessage.tsx

```typescript
// frontend/src/components/chat/ChatMessage.tsx
function CitationMarker({ number, citation, onClick }: CitationMarkerProps) {
  const displayName = citation.file_name.length > 20
    ? citation.file_name.slice(0, 17) + '...'
    : citation.file_name

  return (
    <Tooltip.Provider delayDuration={200}>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <button
            onClick={onClick}
            className="inline-flex items-center px-2 py-0.5 text-xs font-medium bg-primary/10 text-primary rounded-full hover:bg-primary/20 transition-colors mx-0.5 focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label={`Source: ${citation.file_name}`}
          >
            {displayName}
          </button>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="z-50 max-w-sm rounded-md bg-popover px-3 py-2 text-sm text-popover-foreground shadow-md border"
            sideOffset={5}
          >
            <div className="space-y-1">
              <p className="font-medium text-sm">{citation.file_name}</p>
              <p className="text-xs text-muted-foreground">{citation.location}</p>
              <p className="text-xs italic line-clamp-3">"{citation.excerpt}"</p>
            </div>
            <Tooltip.Arrow className="fill-popover" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </Tooltip.Provider>
  )
}
```

### 2. Add SourcesPill and Sidebar Toggle in ChatPage.tsx

```typescript
// frontend/src/pages/ChatPage.tsx

// Add state for sidebar visibility
const [isSourcesOpen, setIsSourcesOpen] = useState(false)

// Sources pill component (inline or extract to separate file)
function SourcesPill({ count, isOpen, onClick }: {
  count: number
  isOpen: boolean
  onClick: () => void
}) {
  if (count === 0) return null

  return (
    <button
      onClick={onClick}
      className="inline-flex items-center gap-2 px-3 py-1.5 text-sm font-medium bg-muted hover:bg-muted/80 rounded-full transition-colors"
      aria-expanded={isOpen}
      aria-label={`${isOpen ? 'Hide' : 'Show'} ${count} sources`}
    >
      <span>Sources ({count})</span>
      <ChevronRight className={cn(
        "w-4 h-4 transition-transform",
        isOpen && "rotate-180"
      )} />
    </button>
  )
}

// In the JSX layout:
<div className="flex flex-1 overflow-hidden">
  {/* Main content */}
  <main className="flex-1 flex flex-col">
    <MessageList ... />

    {/* Sources pill - show above input when citations exist */}
    <div className="px-4 py-2">
      <SourcesPill
        count={citedSources.length}
        isOpen={isSourcesOpen}
        onClick={() => setIsSourcesOpen(!isSourcesOpen)}
      />
    </div>

    <MessageInput ... />
  </main>

  {/* Collapsible right sidebar */}
  <aside className={cn(
    "w-72 border-l border-border flex-shrink-0 transition-all duration-200",
    isSourcesOpen ? "translate-x-0" : "translate-x-full w-0 border-0"
  )}>
    <SourcesPanel
      searchedFiles={searchedFiles}
      citedSources={citedSources}
      onSourceClick={handleCitationClick}
    />
  </aside>
</div>
```

### 3. CSS for Slide Animation

The sidebar uses Tailwind classes:
- `transition-all duration-200` for smooth animation
- `translate-x-0` when open, `translate-x-full w-0` when closed

No additional CSS needed.

## What We're NOT Doing (Per Review Feedback)

| Avoided | Reason |
|---------|--------|
| Vaul dependency | CSS transitions suffice |
| Bottom sheet pattern | Keep familiar sidebar |
| SourceIcon component | File icons add no user value |
| Multiple snap points | 2 states (open/closed) enough |
| Streaming state indicator | Current UX is fine |
| 5-phase implementation | Single PR |

## References

### Files to Modify
- `frontend/src/components/chat/ChatMessage.tsx:115-143` - CitationMarker
- `frontend/src/pages/ChatPage.tsx` - Layout and state

### Existing Components (Reuse)
- `frontend/src/components/sources/SourcesPanel.tsx` - No changes needed
- `frontend/src/components/sources/SourceCard.tsx` - No changes needed
