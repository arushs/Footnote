# refactor: Remove /folders page UI

Remove the `/folders` page UI and simplify the app to only need the chat page. Keep database models and folder API endpoints intact since ChatPage depends on them.

## Acceptance Criteria

- [ ] `/folders` route redirects to `/chat` (preserves bookmarks/browser history)
- [ ] Authenticated users redirect to `/chat` after login (not `/folders`)
- [ ] Header logo links to `/chat`
- [ ] ChatPage back navigation removed (no parent page)
- [ ] FoldersPage.tsx deleted
- [ ] DELETE `/api/folders/{id}` endpoint removed (folder deletion is database-only)
- [ ] All other folder endpoints kept (needed by ChatPage)
- [ ] Unit tests updated (Layout.test.tsx assertions fixed)
- [ ] E2E tests updated (FoldersPage tests deleted, flows rewritten)
- [ ] `npm run lint` passes
- [ ] `npm run build` succeeds
- [ ] `npm test` passes
- [ ] E2E tests pass

## Context

**Why:** The folders page is no longer needed. Users can select folders from ChatPage's EmptyState dropdown and add folders from the AddFolderDropdown component in the sidebar.

**Product Decision:** Folder deletion will be database/admin-only. Users cannot delete folders from the UI. This simplifies the app but means folder cleanup is a manual process.

**What stays:**
- Database models and tables (Folder, File, Conversation, etc.)
- Folder API endpoints (all needed by ChatPage):
  - `GET /api/folders` - EmptyState dropdown population
  - `POST /api/folders` - AddFolderDropdown creates folders
  - `GET /api/folders/{id}` - useFolderStatus hook
  - `GET /api/folders/{id}/status` - indexing progress polling

**What goes:**
- FoldersPage.tsx (UI)
- `DELETE /api/folders/{id}` (no UI calls this)
- Navigation links to `/folders`
- FoldersPage-specific tests

## Implementation Steps

### Frontend

#### 1. App.tsx
- Remove FoldersPage import
- Remove `/folders` `<Route>` component
- Add redirect: `<Route path="/folders" element={<Navigate to="/chat" replace />} />`

#### 2. LandingPage.tsx
- Change authenticated redirect from `/folders` to `/chat`

#### 3. Header.tsx
- Change brand `<Link to="/folders">` to `<Link to="/chat">`

#### 4. ChatPage.tsx
- Remove `backTo="/folders"` prop from Header.Brand
- Remove `backLabel="Folders"` prop from Header.Brand

#### 5. pages/index.ts
- Remove `export { FoldersPage } from './FoldersPage'`

#### 6. FoldersPage.tsx
- **DELETE entire file**

#### 7. Layout.test.tsx (Unit Tests)
- Update line 216: Change `href` assertion from `/folders` to `/chat`
- Update lines 186, 198: Change test `backTo` values to a valid test path (e.g., `/`)

#### 8. happy-path.spec.ts (E2E)
- **Rewrite first test** (`can select folder and ask question`):
  - Start from `/chat` instead of `/folders`
  - Use EmptyState dropdown to select folder instead of clicking folder card
  - Assert navigation to `/chat/{folderId}`
- Keep second and third tests unchanged (they already start from `/chat/{id}`)

#### 9. errors.spec.ts (E2E)
- **DELETE** the two tests that test FoldersPage UI:
  - `shows error for inaccessible folder`
  - `shows failed status for folder with indexing error`
- These test removed functionality

### Backend

#### 1. routes/folders.py
- Remove `delete_folder` endpoint function (lines 189-213)
- Keep all other endpoints

#### 2. tests/test_folders.py
- Remove entire `TestDeleteFolder` class (5 test methods)
- Keep all other test classes

## Files to Modify

| File | Action |
|------|--------|
| `frontend/src/App.tsx` | Edit - remove route, add redirect |
| `frontend/src/pages/LandingPage.tsx` | Edit - change redirect target |
| `frontend/src/pages/FoldersPage.tsx` | **DELETE** |
| `frontend/src/pages/index.ts` | Edit - remove export |
| `frontend/src/components/layout/Header.tsx` | Edit - change link target |
| `frontend/src/pages/ChatPage.tsx` | Edit - remove back nav props |
| `frontend/src/components/__tests__/Layout.test.tsx` | Edit - update assertions |
| `frontend/e2e/happy-path.spec.ts` | Edit - rewrite first test |
| `frontend/e2e/errors.spec.ts` | Edit - delete FoldersPage tests |
| `backend/app/routes/folders.py` | Edit - remove DELETE endpoint |
| `backend/tests/test_folders.py` | Edit - remove TestDeleteFolder class |

## Files Verified Unchanged

These files were reviewed and need no changes:
- `frontend/src/hooks/useFolderStatus.ts` - Uses kept endpoints
- `frontend/src/hooks/useConversations.ts` - Uses chat.py endpoints
- `frontend/src/components/sidebar/AddFolderDropdown.tsx` - Uses `POST /api/folders` (kept)
- `backend/main.py` - folders router still needed for remaining endpoints

## Verification Commands

After implementation, run:
```bash
cd frontend && npm run lint && npm run build && npm test
cd ../backend && pytest
cd ../frontend && npm run e2e
```

## References

- `frontend/src/App.tsx` - Route definition (grep: `path="/folders"`)
- `frontend/src/pages/LandingPage.tsx` - Redirect (grep: `navigate('/folders')`)
- `frontend/src/components/layout/Header.tsx` - Brand link (grep: `to="/folders"`)
- `frontend/src/pages/ChatPage.tsx` - Back nav (grep: `backTo=`)
- `frontend/src/components/__tests__/Layout.test.tsx` - Assertions (grep: `/folders`)
- `frontend/e2e/errors.spec.ts` - FoldersPage tests (grep: `Your Folders`)
- `backend/app/routes/folders.py` - DELETE endpoint (grep: `@router.delete`)
- `backend/tests/test_folders.py` - Delete tests (grep: `TestDeleteFolder`)
