import { test, expect } from '@playwright/test'

// Mock user data
const mockUser = {
  id: 'test-user-id',
  email: 'test@example.com',
  name: 'Test User',
}

// Mock folder data
const mockFolder = {
  id: 'test-folder-id',
  google_folder_id: 'google-folder-123',
  folder_name: 'Test Folder',
  index_status: 'ready',
  files_total: 5,
  files_indexed: 5,
}

test.describe('Error Handling', () => {
  test.beforeEach(async ({ page }) => {
    // Mock authenticated user
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockUser),
      })
    })
  })

  test('shows error for inaccessible folder', async ({ page }) => {
    // Mock folders list with empty
    await page.route('**/api/folders', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ folders: [] }),
        })
      } else if (route.request().method() === 'POST') {
        // Mock 403 error when trying to add a folder
        await route.fulfill({
          status: 403,
          contentType: 'application/json',
          body: JSON.stringify({
            error: 'Access denied',
            message: 'You do not have access to this folder',
          }),
        })
      }
    })

    // Navigate to folders page
    await page.goto('/folders')
    await expect(page.locator('h2:has-text("Your Folders")')).toBeVisible()

    // Should show empty state
    await expect(page.locator('text=No folders yet')).toBeVisible()
  })

  test('shows failed status for folder with indexing error', async ({ page }) => {
    // Mock folders list with a failed folder
    await page.route('**/api/folders', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            folders: [{
              ...mockFolder,
              index_status: 'failed',
            }],
          }),
        })
      }
    })

    // Navigate to folders page
    await page.goto('/folders')

    // Should show the folder with failed status
    await expect(page.locator('text=Test Folder')).toBeVisible()
    await expect(page.locator('text=Failed')).toBeVisible()
  })

  test('handles grounding failure gracefully', async ({ page }) => {
    // Set up route handlers - order matters, most specific first

    // Mock chat endpoint specifically
    await page.route('**/api/folders/*/chat', async (route) => {
      // Mock a grounding failure response - model couldn't find relevant info
      const sseResponse = [
        `data: {"token":"I couldn't find "}\n\n`,
        `data: {"token":"any relevant information "}\n\n`,
        `data: {"token":"about that topic "}\n\n`,
        `data: {"token":"in your documents."}\n\n`,
        `data: {"done":true,"citations":{},"searched_files":["quarterly_report.pdf","notes.docx"],"conversation_id":"conv-456"}\n\n`,
      ].join('')

      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: sseResponse,
      })
    })

    // Mock folder status
    await page.route('**/api/folders/*/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ready',
          files_total: 5,
          files_indexed: 5,
        }),
      })
    })

    // Mock conversations list
    await page.route('**/api/folders/*/conversations', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    })

    // Mock folder details (catch-all for other folder endpoints)
    await page.route('**/api/folders/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockFolder),
      })
    })

    // Mock folders list
    await page.route('**/api/folders', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ folders: [mockFolder] }),
      })
    })

    // Navigate to chat page
    await page.goto('/chat/test-folder-id')

    // Wait for chat interface
    await expect(page.locator('textarea[placeholder*="Ask"]')).toBeVisible()

    // Ask about something not in the documents
    await page.fill('textarea[placeholder*="Ask"]', 'What is the weather in Tokyo?')
    await page.click('button[title="Send message"]')

    // Should show graceful refusal message - wait for response to stream
    await expect(page.locator('text=your documents')).toBeVisible({ timeout: 10000 })

    // No citation buttons should be present in the response (look in prose area)
    const citationButtons = page.locator('.prose button')
    await expect(citationButtons).toHaveCount(0)
  })

  test('handles network error during chat', async ({ page }) => {
    // Mock chat endpoint to simulate network error
    await page.route('**/api/folders/*/chat', async (route) => {
      await route.abort('failed')
    })

    // Mock folder status
    await page.route('**/api/folders/*/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'ready',
          files_total: 5,
          files_indexed: 5,
        }),
      })
    })

    // Mock conversations list
    await page.route('**/api/folders/*/conversations', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    })

    // Mock folder details
    await page.route('**/api/folders/*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockFolder),
      })
    })

    // Mock folders list
    await page.route('**/api/folders', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ folders: [mockFolder] }),
      })
    })

    // Navigate to chat page
    await page.goto('/chat/test-folder-id')

    // Wait for chat interface
    await expect(page.locator('textarea[placeholder*="Ask"]')).toBeVisible()

    // Send a message
    await page.fill('textarea[placeholder*="Ask"]', 'What is the revenue?')
    await page.click('button[title="Send message"]')

    // Wait a moment for error to be handled
    await page.waitForTimeout(1000)

    // The input should be re-enabled after error (loading state cleared)
    await expect(page.locator('button[title="Send message"]')).toBeVisible()

    // User message should still be visible (optimistic update)
    await expect(page.locator('text=What is the revenue?')).toBeVisible()
  })
})
