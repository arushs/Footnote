# Plan: Add Comprehensive Test Coverage

## Overview
Add tests for all untested features across frontend hooks, components, and backend services.

## Test Convention
- **Colocated tests**: Test files live alongside source files (e.g., `useChat.ts` → `useChat.test.ts`)
- **Framework**: Vitest + React Testing Library (frontend), pytest (backend)

---

## Frontend Hooks

### 1. `useConversations.test.ts` ✅ DONE
- Initial state (loading, empty conversations)
- Fetch on mount with correct folder ID
- Error handling (network errors, API failures)
- Refetch functionality
- Disabled state

### 2. `useFolderStatus.test.ts` ✅ DONE
- Initial state
- Fetch folder and status
- Status flags (isReady, isIndexing, isFailed)
- Progress calculation (0%, 50%, 100%)
- Polling behavior during indexing
- onIndexingComplete callback
- Error handling

### 3. `useGooglePicker.test.ts` ✅ DONE
- Configuration validation (missing API keys)
- Script loading state
- Error when APIs not loaded
- Mocked Google API interactions

### 4. `AuthContext.test.tsx` ✅ DONE
- useAuth throws outside provider
- Initial loading state
- Successful auth check
- Failed auth (401, network error)
- Logout clears user

---

## Frontend Components

### 5. `MessageInput.test.tsx` ✅ DONE
- Renders with default/custom placeholder
- Send/stop button states
- Input updates on typing
- Disabled state
- Send with trimmed message
- Clear input after send
- Empty/whitespace message prevention
- Enter key sends, Shift+Enter adds newline
- Stop button calls onStop

### 6. `MessageList.test.tsx`
- Empty state with "Start a conversation" message
- Renders list of messages
- Renders streaming message when loading
- Loading indicator (bouncing dots) when loading without content
- Passes onCitationClick to ChatMessage
- Accessibility: role="log", aria-live="polite"

### 7. `StreamingMessage.test.tsx`
- Renders content text
- Shows pulsing cursor
- Bot icon displayed

### 8. `ChatHistory.test.tsx`
- Header with folder name
- New Chat button triggers onNewConversation
- Loading skeleton state
- Empty state ("No conversations yet")
- Renders conversation list
- Active conversation highlighted
- Date formatting (Just now, Xm ago, Xh ago, Xd ago, date)

### 9. `ConversationList.test.tsx`
- Loading skeleton
- Empty state
- Renders conversations
- Click selects conversation
- Active state styling
- Date formatting

### 10. `SourcesPanel.test.tsx`
- Empty state ("Sources will appear here")
- Cited sources section with cards
- Searched files section
- Source card click triggers onSourceClick
- External link opens Google Drive URL
- Accessibility labels

### 11. `IndexingProgress.test.tsx`
- Returns null when status is ready
- Shows progress bar and percentage
- Pending state message
- Indexing state message
- Failed state with error message and retry button
- IndexingComplete component with dismiss button

### 12. `AddFolderDropdown.test.tsx`
- Dropdown opens/closes
- Renders options

---

## Backend Services

### 13. `test_retrieval.py`
- `format_vector()` - converts list to PostgreSQL vector string
- `vector_search()` - returns chunks ordered by similarity
- `retrieve_and_rerank()` - two-stage retrieval
- `format_context_for_llm()` - formats chunks with source markers
- `_format_location()` - PDF pages, doc headings

### 14. `test_drive.py`
- `DriveService.list_files()` - pagination, returns FileMetadata
- `DriveService.get_file_metadata()` - single file
- `DriveService.export_google_doc()` - exports to HTML
- `DriveService.download_file()` - binary download
- Error handling (HTTP errors)
- Shared HTTP client reuse

### 15. `test_generation.py`
- `parse_citations()` - extracts [N] citations
- `parse_citations()` - excludes array indexing (array[0])
- `parse_citations()` - handles no citations
- `parse_citations()` - multiple citations
- `extract_citation_numbers()` - returns unique set

---

## Implementation Order

### Phase 1: Frontend Components (5 files)
1. MessageList.test.tsx
2. StreamingMessage.test.tsx
3. ChatHistory.test.tsx
4. ConversationList.test.tsx
5. SourcesPanel.test.tsx
6. IndexingProgress.test.tsx

### Phase 2: Backend Services (3 files)
1. test_retrieval.py
2. test_drive.py
3. test_generation.py

---

## Commit Strategy
- Commit after each phase
- Format: `test: Add [component/service] tests`

---

## Status
- [x] Frontend hooks (4/4)
- [x] AuthContext
- [x] MessageInput
- [ ] MessageList
- [ ] StreamingMessage
- [ ] ChatHistory
- [ ] ConversationList
- [ ] SourcesPanel
- [ ] IndexingProgress
- [ ] Backend retrieval
- [ ] Backend drive
- [ ] Backend generation
