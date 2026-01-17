# feat: Chat-First Empty State with Folder Selection

## Overview

Transform the `/chat` page to allow users to start a conversation directly, without requiring pre-navigation to a folder page. The new empty state displays a centered textbox with folder selection, creating the conversation lazily on the first message.

## Problem Statement / Motivation

**Current State:**
- `/chat` without a `folderId` shows an empty state with "No folder selected" message
- Users must navigate to `/folders` first, then click a folder to start chatting
- This creates an unnecessary extra step in the user journey

**Proposed State:**
- `/chat` shows a centered, inviting textbox with folder dropdown
- Users select a folder from a dropdown (plus option to add new folders)
- Conversation is created lazily when the first message is sent
- Matches patterns from ChatGPT, Claude, and Gemini empty states

## Proposed Solution

### User Flow

```
User visits /chat
    └── Sees centered card with:
        ├── Folder dropdown (required before sending)
        ├── Text input (disabled until folder selected)
        └── Add new folder link

User selects folder from dropdown
    └── Input becomes enabled
    └── Sidebars appear (ChatHistory, SourcesPanel)
    └── URL updates to /chat/{folderId}

User sends first message
    └── Conversation created via POST /api/folders/{folderId}/chat
    └── Response streams back
    └── Conversation appears in ChatHistory sidebar
```

### Key Design Decisions

1. **Folder is required before sending** - The backend API requires `folderId`, so folder selection is mandatory. The send button is disabled until a folder is selected.

2. **URL updates on folder selection** - When user selects a folder, navigate to `/chat/{folderId}` using `navigate()` (not `replaceState`). This matches the current pattern and enables back button functionality.

3. **Sidebars appear after folder selection** - Once a folder is selected, the full chat UI with sidebars appears, matching the existing `/chat/:folderId` experience.

4. **Lazy conversation creation** - Already implemented in `useChat.ts` - conversations are created on first message, not on folder selection.

## Technical Considerations

### Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/pages/ChatPage.tsx` | Rewrite `EmptyState` section with new UI |
| `frontend/src/hooks/useFolders.ts` | **NEW** - Hook to fetch folders list |
| `frontend/src/components/chat/FolderSelector.tsx` | **NEW** - Dropdown component for folder selection |

### Architecture

```
ChatPage.tsx
├── No folderId?
│   └── ChatEmptyState (new component)
│       ├── FolderSelector dropdown
│       ├── MessageInput (disabled until folder selected)
│       └── Add folder link
└── Has folderId?
    └── Full chat UI (unchanged)
```

### Component: FolderSelector

```tsx
// frontend/src/components/chat/FolderSelector.tsx
interface FolderSelectorProps {
  folders: Folder[]
  selectedFolderId: string | null
  onSelect: (folderId: string) => void
  onAddFolder: () => void
  isLoading?: boolean
}
```

Features:
- Radix UI `Select` component for accessibility
- Shows folder name + status indicator (ready/indexing)
- Disabled folders that are still indexing
- "Add new folder" option at bottom

### Hook: useFolders

```typescript
// frontend/src/hooks/useFolders.ts
export function useFolders() {
  const [folders, setFolders] = useState<Folder[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  // Fetch folders on mount
  // Provide addFolder function (reuse Google Picker logic)
  // Provide refreshFolders function

  return { folders, isLoading, error, addFolder, refreshFolders }
}
```

### UI Layout (Empty State)

```
+--------------------------------------------------+
|  [Logo] Rig           [Folders]      [User Menu] |
+--------------------------------------------------+
|                                                  |
|                                                  |
|          +-----------------------------+         |
|          |                             |         |
|          |    How can I help you?      |         |
|          |                             |         |
|          |  +------------------------+ |         |
|          |  | Select a folder...   v | |         |
|          |  +------------------------+ |         |
|          |                             |         |
|          |  +------------------------+ |         |
|          |  | Ask about your files   | |         |
|          |  |                      > | |         |
|          |  +------------------------+ |         |
|          |                             |         |
|          |  + Add a new folder         |         |
|          |                             |         |
|          +-----------------------------+         |
|                                                  |
|                                                  |
+--------------------------------------------------+
```

## Acceptance Criteria

### Functional Requirements

- [ ] `/chat` page displays centered empty state with folder dropdown
- [ ] Folder dropdown shows all user's folders with status indicators
- [ ] Indexing folders are visible but disabled in dropdown
- [ ] Selecting a folder navigates to `/chat/{folderId}`
- [ ] "Add new folder" triggers Google Picker flow
- [ ] After adding folder, automatically select it and navigate
- [ ] Message input is disabled until folder is selected
- [ ] Placeholder text guides user: "Select a folder to start chatting..."

### Edge Cases

- [ ] User with no folders sees "Add a folder" as primary action
- [ ] User with all folders indexing sees appropriate message
- [ ] Network error when fetching folders shows retry option
- [ ] Google Picker failure shows error toast

### Non-Functional Requirements

- [ ] Folder dropdown loads within 200ms
- [ ] Keyboard accessible (Tab through folder dropdown and input)
- [ ] Screen reader announces folder selection changes

## Implementation Phases

### Phase 1: Create useFolders Hook

1. Create `frontend/src/hooks/useFolders.ts`
2. Extract folder fetching logic from `FoldersPage.tsx`
3. Include `addFolder` function with Google Picker integration
4. Add error handling and loading states

### Phase 2: Create FolderSelector Component

1. Create `frontend/src/components/chat/FolderSelector.tsx`
2. Use Radix UI `Select` primitive
3. Show folder name, status indicator
4. Disable indexing folders with tooltip explanation
5. Add "Add new folder" option

### Phase 3: Update ChatPage Empty State

1. Replace current `EmptyState` JSX in `ChatPage.tsx`
2. Integrate `FolderSelector` component
3. Add centered layout with proper styling
4. Connect to navigation on folder selection
5. Ensure proper input disabled state

### Phase 4: Polish & Testing

1. Add keyboard navigation support
2. Test screen reader announcements
3. Handle all error states
4. Test with 0, 1, many folders
5. Test with indexing/failed folders

## Dependencies & Prerequisites

- Existing `useGooglePicker` hook for folder creation
- Existing `AddFolderDropdown` component (may reuse logic)
- Radix UI `Select` component (already installed)

## Success Metrics

- Users can start chatting from `/chat` in 2 clicks (select folder + send message)
- Reduced bounce rate from `/chat` page
- No increase in support tickets about "can't start a chat"

## References & Research

### Internal References

- Chat page component: `frontend/src/pages/ChatPage.tsx:13-39` (current EmptyState)
- Chat hook with lazy creation: `frontend/src/hooks/useChat.ts:49-51`
- Google Picker integration: `frontend/src/hooks/useGooglePicker.ts`
- Folder dropdown: `frontend/src/components/sidebar/AddFolderDropdown.tsx`
- Message input: `frontend/src/components/chat/MessageInput.tsx`

### External References

- [Radix UI Select](https://www.radix-ui.com/primitives/docs/components/select)
- [ChatGPT empty state pattern](https://chat.openai.com)
- [Claude empty state pattern](https://claude.ai)

### Best Practices Applied

- Lazy conversation creation (already implemented)
- Centered hero-style layout for new conversations
- Progressive disclosure (sidebars appear after folder selection)
- Disabled states with clear guidance
