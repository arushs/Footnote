# Frontend Design Plan: "Footnote"

> **Aesthetic Direction**: "Digital Archive" - refined editorial aesthetic inspired by museum archives and modernist design. Swiss typography precision meets paper document warmth.

## Overview

Transform the basic UI into a distinctive, accessible application with Google Drive folder picker integration.

---

## 1. Component Architecture

```
src/
├── components/
│   ├── ui/                      # Base primitives
│   │   ├── button.tsx           # Existing, needs refinement
│   │   ├── input.tsx            # New - styled input with focus states
│   │   ├── card.tsx             # New - folder-tab styled cards
│   │   ├── dialog.tsx           # Wrap Radix Dialog
│   │   ├── scroll-area.tsx      # Wrap Radix ScrollArea
│   │   └── tooltip.tsx          # Wrap Radix Tooltip
│   │
│   ├── layout/
│   │   ├── AppShell.tsx         # Main layout wrapper
│   │   ├── Sidebar.tsx          # Collapsible sidebar
│   │   └── Header.tsx           # Top navigation bar
│   │
│   ├── auth/
│   │   ├── GoogleSignInButton.tsx
│   │   └── UserMenu.tsx         # Dropdown with avatar
│   │
│   ├── drive/
│   │   ├── FolderPicker.tsx     # Google Picker integration
│   │   ├── FolderCard.tsx       # Display selected folder
│   │   └── FolderList.tsx       # List of indexed folders
│   │
│   ├── chat/
│   │   ├── MessageList.tsx      # Scrollable messages
│   │   ├── MessageBubble.tsx    # Individual message
│   │   ├── ChatInput.tsx        # Textarea with send button
│   │   ├── SourceCard.tsx       # Citation/source display
│   │   └── TypingIndicator.tsx  # Loading state
│   │
│   └── history/
│       ├── ConversationList.tsx
│       └── ConversationItem.tsx
│
├── pages/
│   ├── Landing.tsx              # Sign-in page
│   ├── FolderSelect.tsx         # NEW - folder picker page
│   └── Chat.tsx                 # Main chat interface
│
├── hooks/
│   ├── useAuth.ts               # Auth state management
│   ├── useGooglePicker.ts       # Drive picker hook
│   ├── useFolders.ts            # Folder CRUD operations
│   └── useChat.ts               # Chat state & streaming
│
├── lib/
│   ├── utils.ts                 # Existing cn() helper
│   ├── api.ts                   # API client
│   └── google-picker.ts         # Picker initialization
│
└── styles/
    └── index.css                # Enhanced CSS variables
```

---

## 2. User Flow

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Landing   │────▶│  Folder Select   │────▶│      Chat       │
│  (Sign In)  │     │  (Pick Folder)   │     │  (Conversation) │
└─────────────┘     └──────────────────┘     └─────────────────┘
                            │                         │
                            │ Can return to           │ Can switch
                            │ add more folders        │ folders
                            ▼                         ▼
                    ┌──────────────────┐     ┌─────────────────┐
                    │  Indexing State  │     │  Source Panel   │
                    │  (Processing)    │     │  (Citations)    │
                    └──────────────────┘     └─────────────────┘
```

**Flow Details:**
1. **Landing** → User sees value prop, signs in with Google
2. **Folder Select** → NEW page where user picks Drive folders to index
3. **Indexing** → Show progress while files are processed
4. **Chat** → Main interface with folder context, chat, and sources

---

## 3. Visual Design System

### Color Palette (CSS Variables)

```css
:root {
  /* Core - Warm paper tones */
  --background: 48 30% 98%;        /* Off-white, paper-like */
  --foreground: 30 10% 15%;        /* Warm dark brown/black */

  /* Surface layers */
  --card: 45 25% 96%;              /* Slightly cream */
  --card-elevated: 0 0% 100%;      /* Pure white for contrast */

  /* Accent - Deep archive blue */
  --primary: 220 65% 28%;          /* Refined navy */
  --primary-foreground: 0 0% 98%;

  /* Secondary - Folder manila */
  --secondary: 42 45% 88%;         /* Manila folder color */
  --secondary-foreground: 30 10% 25%;

  /* Functional */
  --muted: 40 15% 92%;
  --muted-foreground: 30 8% 45%;
  --border: 35 20% 88%;
  --ring: 220 65% 28%;

  /* Accents */
  --success: 145 45% 35%;
  --warning: 38 90% 50%;
  --destructive: 0 65% 50%;
}

.dark {
  --background: 30 15% 8%;         /* Warm dark */
  --foreground: 40 15% 92%;
  --card: 30 12% 12%;
  --primary: 215 55% 55%;          /* Lighter blue */
  --secondary: 35 25% 20%;
}
```

### Typography

```css
/* Display: Editorial serif for headings */
@import url('https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&display=swap');

/* Body: Clean geometric sans */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&display=swap');

:root {
  --font-display: 'Newsreader', Georgia, serif;
  --font-body: 'DM Sans', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
}
```

### Visual Motifs

- **Folder tabs**: Cards have a tab-like protrusion on top-left
- **Paper texture**: Subtle noise overlay on backgrounds
- **Corner accents**: Decorative corner brackets on key elements
- **Layered depth**: Stacked card effect to suggest documents

---

## 4. Accessibility (WCAG 2.1 AA)

### Requirements

- **Color contrast**: All text meets 4.5:1 ratio
- **Focus indicators**: Visible 2px ring on all interactive elements
- **Keyboard navigation**: Full tab order, arrow keys in menus
- **Screen readers**: Proper ARIA labels, live regions for chat

### Implementation Examples

```tsx
// Focus-visible styling
<button className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2">

// ARIA live region for new messages
<div role="log" aria-live="polite" aria-label="Chat messages">

// Proper labeling
<input aria-label="Message input" aria-describedby="input-hint" />
<span id="input-hint" className="sr-only">Press Enter to send</span>

// Skip link for keyboard users
<a href="#main-content" className="sr-only focus:not-sr-only">
  Skip to main content
</a>
```

### Motion

- Respect `prefers-reduced-motion`
- Keep animations under 200ms for UI feedback
- No auto-playing animations

---

## 5. Google Drive Picker Integration

### Hook Implementation

```tsx
// hooks/useGooglePicker.ts
import { useCallback, useEffect, useState } from 'react'

export function useGooglePicker() {
  const [pickerLoaded, setPickerLoaded] = useState(false)
  const [accessToken, setAccessToken] = useState<string | null>(null)

  // Load the Google Picker API
  useEffect(() => {
    const script = document.createElement('script')
    script.src = 'https://apis.google.com/js/api.js'
    script.onload = () => {
      window.gapi.load('picker', () => setPickerLoaded(true))
    }
    document.body.appendChild(script)
  }, [])

  // Get access token from our backend after OAuth
  useEffect(() => {
    fetch('/api/auth/token')
      .then(res => res.json())
      .then(data => setAccessToken(data.access_token))
      .catch(console.error)
  }, [])

  const openPicker = useCallback(
    (onSelect: (folderId: string, folderName: string) => void) => {
      if (!pickerLoaded || !accessToken) return

      const picker = new window.google.picker.PickerBuilder()
        .addView(
          new window.google.picker.DocsView()
            .setIncludeFolders(true)
            .setSelectFolderEnabled(true)
            .setMimeTypes('application/vnd.google-apps.folder')
        )
        .setOAuthToken(accessToken)
        .setDeveloperKey(import.meta.env.VITE_GOOGLE_API_KEY)
        .setCallback((data: google.picker.ResponseObject) => {
          if (data.action === 'picked') {
            const folder = data.docs[0]
            onSelect(folder.id, folder.name)
          }
        })
        .setTitle('Select a folder to chat with')
        .build()

      picker.setVisible(true)
    },
    [pickerLoaded, accessToken]
  )

  return { openPicker, isReady: pickerLoaded && !!accessToken }
}
```

### Component

```tsx
// components/drive/FolderPicker.tsx
import { FolderOpen, Plus } from 'lucide-react'
import { useGooglePicker } from '@/hooks/useGooglePicker'
import { Button } from '@/components/ui/button'

interface FolderPickerProps {
  onFolderSelect: (folderId: string, name: string) => void
}

export function FolderPicker({ onFolderSelect }: FolderPickerProps) {
  const { openPicker, isReady } = useGooglePicker()

  return (
    <Button
      onClick={() => openPicker(onFolderSelect)}
      disabled={!isReady}
      variant="secondary"
      size="lg"
      className="group relative"
    >
      <FolderOpen className="mr-2 h-5 w-5 transition-transform group-hover:scale-110" />
      Choose from Google Drive
      <Plus className="absolute -right-1 -top-1 h-4 w-4 rounded-full bg-primary text-primary-foreground" />
    </Button>
  )
}
```

---

## 6. Page Wireframes

### Landing Page

```
┌────────────────────────────────────────────────────┐
│                                                    │
│     ┌─ decorative corner bracket                   │
│     │                                              │
│         "Footnote"  ← Newsreader serif    │
│                                                    │
│     Your documents, conversational.                │
│     Ask questions. Get answers with sources.       │
│                                                    │
│     ┌──────────────────────────────┐              │
│     │  ▶  Continue with Google     │              │
│     └──────────────────────────────┘              │
│                                                    │
│     [Feature cards with folder-tab styling]        │
│     ┌─┐                ┌─┐               ┌─┐      │
│     │ │ Select         │ │ Ask           │ │ Get  │
│     │ │ Folders        │ │ Questions     │ │ Sources│
│     └─┴────────────┘   └─┴──────────┘    └─┴──────┘│
│                                                    │
└────────────────────────────────────────────────────┘
```

### Folder Select Page (NEW)

```
┌────────────────────────────────────────────────────┐
│  ← Back    Footnote    [User Menu ▼]         │
├────────────────────────────────────────────────────┤
│                                                    │
│     Select folders to chat with                    │
│                                                    │
│     ┌─────────────────────────────────────────┐   │
│     │  ┌─┐                                    │   │
│     │  │+│  Add folder from Google Drive      │   │
│     │  └─┘  Click to open picker              │   │
│     └─────────────────────────────────────────┘   │
│                                                    │
│     Your folders (2)                               │
│     ┌─┐                      ┌─┐                  │
│     │ │ Project Docs         │ │ Research Notes   │
│     │ │ 24 files • Ready     │ │ 12 files • Indexing...│
│     │ │ [Chat] [Remove]      │ │ [██████░░░] 60% │
│     └─┴────────────────────┘ └─┴────────────────┘│
│                                                    │
└────────────────────────────────────────────────────┘
```

### Chat Page (Refined)

```
┌──────────────────────────────────────────────────────────┐
│  ☰  Project Docs ▼          Footnote    [User ▼]  │
├─────────┬────────────────────────────────┬───────────────┤
│         │                                │               │
│ History │   ┌─────────────────────┐      │   Sources     │
│         │   │ What's the main     │ You  │               │
│ • Chat 1│   │ theme of these docs?│      │   ┌─┐         │
│ • Chat 2│   └─────────────────────┘      │   │ │ doc.pdf │
│ • Chat 3│                                │   │ │ p.12    │
│         │   ┌─────────────────────┐      │   └─┴─────────│
│ ────────│   │ Based on your docs, │ AI   │               │
│ + New   │   │ the main theme is...│      │   ┌─┐         │
│         │   │ [1] [2]             │      │   │ │ notes   │
│         │   └─────────────────────┘      │   │ │ p.3     │
│         │                                │   └─┴─────────│
│         ├────────────────────────────────┤               │
│         │ ┌────────────────────────────┐ │               │
│         │ │ Ask about your files...    │ │               │
│         │ └────────────────────────────┘ │               │
└─────────┴────────────────────────────────┴───────────────┘
```

---

## 7. Implementation Phases

### Phase 1: Foundation
- [ ] Update CSS variables and typography in `index.css`
- [ ] Create base UI components (Input, Card, Dialog)
- [ ] Implement layout components (AppShell, Sidebar, Header)

### Phase 2: Auth & Drive Integration
- [ ] Google Picker hook and component
- [ ] Folder Select page with routing
- [ ] User menu with auth state
- [ ] Backend endpoint for access token retrieval

### Phase 3: Chat Interface
- [ ] Message components with proper styling
- [ ] Source cards with document previews
- [ ] Chat input with streaming support
- [ ] Conversation history sidebar

### Phase 4: Polish
- [ ] Animations and micro-interactions
- [ ] Loading states and skeletons
- [ ] Error handling UI
- [ ] Dark mode refinement
- [ ] Mobile responsiveness

---

## 8. Type Definitions

```tsx
// types/google-picker.d.ts
declare namespace google.picker {
  class PickerBuilder {
    addView(view: DocsView): PickerBuilder
    setOAuthToken(token: string): PickerBuilder
    setDeveloperKey(key: string): PickerBuilder
    setCallback(callback: (data: ResponseObject) => void): PickerBuilder
    setTitle(title: string): PickerBuilder
    build(): Picker
  }

  class DocsView {
    setIncludeFolders(include: boolean): DocsView
    setSelectFolderEnabled(enabled: boolean): DocsView
    setMimeTypes(types: string): DocsView
  }

  interface Picker {
    setVisible(visible: boolean): void
  }

  interface ResponseObject {
    action: 'picked' | 'cancel'
    docs: Array<{
      id: string
      name: string
      mimeType: string
    }>
  }
}

declare global {
  interface Window {
    gapi: {
      load: (api: string, callback: () => void) => void
    }
    google: {
      picker: typeof google.picker
    }
  }
}
```

---

## Notes

- The "Digital Archive" aesthetic differentiates from generic AI tools
- Folder-tab motif creates visual cohesion tied to the core metaphor
- All components should be built with accessibility-first approach
- Consider adding Framer Motion for page transitions in Phase 4
