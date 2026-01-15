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

// Mock citation data
const mockCitation = {
  chunk_id: 'chunk-1',
  file_name: 'quarterly_report.pdf',
  location: 'Page 3',
  excerpt: 'Q4 revenue reached $4.2 million, representing a 25% increase year-over-year.',
  google_drive_url: 'https://drive.google.com/file/d/abc123/view',
}

test.describe('Talk to Folder - Happy Path', () => {
  test.beforeEach(async ({ page }) => {
    // Mock authenticated user
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockUser),
      })
    })

    // Mock folders list
    await page.route('**/api/folders', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ folders: [mockFolder] }),
        })
      } else {
        await route.continue()
      }
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

    // Mock folder details
    await page.route('**/api/folders/*', async (route) => {
      if (route.request().method() === 'GET' && !route.request().url().includes('/chat') && !route.request().url().includes('/status')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(mockFolder),
        })
      } else {
        await route.continue()
      }
    })

    // Mock conversations
    await page.route('**/api/folders/*/conversations', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      })
    })
  })

  test('can select folder from dropdown and ask question', async ({ page }) => {
    // Mock chat streaming response
    await page.route('**/api/folders/*/chat', async (route) => {
      const sseResponse = [
        'data: {"token":"The "}\n\n',
        'data: {"token":"revenue "}\n\n',
        'data: {"token":"was "}\n\n',
        'data: {"token":"$4.2M "}\n\n',
        'data: {"token":"[1]."}\n\n',
        `data: {"done":true,"citations":{"1":${JSON.stringify(mockCitation)}},"searched_files":["quarterly_report.pdf"],"conversation_id":"conv-123"}\n\n`,
      ].join('')

      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: sseResponse,
      })
    })

    // Navigate to chat page (empty state)
    await page.goto('/chat')

    // Should show empty state with folder dropdown
    await expect(page.locator('h2:has-text("How can I help you?")')).toBeVisible()

    // Open the folder dropdown
    await page.click('button:has-text("Select a folder...")')

    // Should show the test folder in dropdown
    await expect(page.locator('[role="menuitem"]:has-text("Test Folder")')).toBeVisible()

    // Select the folder
    await page.click('[role="menuitem"]:has-text("Test Folder")')

    // Should navigate to chat page with folder
    await expect(page).toHaveURL(/\/chat\/test-folder-id/)

    // Wait for chat interface to load
    await expect(page.locator('textarea[placeholder*="Ask"]')).toBeVisible()

    // Type a question
    await page.fill('textarea[placeholder*="Ask"]', 'What was the Q4 revenue?')

    // Send the message
    await page.click('button[title="Send message"]')

    // Wait for response with citation
    await expect(page.locator('text=$4.2M')).toBeVisible({ timeout: 10000 })

    // Citation marker should be visible (use more specific selector for citation button)
    await expect(page.locator('.prose button:has-text("1")')).toBeVisible()
  })

  test('citation hover shows tooltip', async ({ page }) => {
    // Set up mocks for a conversation with existing messages
    await page.route('**/api/folders/*/chat', async (route) => {
      const sseResponse = [
        'data: {"token":"Revenue was $4.2M [1]."}\n\n',
        `data: {"done":true,"citations":{"1":${JSON.stringify(mockCitation)}},"searched_files":["quarterly_report.pdf"],"conversation_id":"conv-123"}\n\n`,
      ].join('')

      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: sseResponse,
      })
    })

    // Navigate to chat page
    await page.goto('/chat/test-folder-id')

    // Type and send a question
    await page.fill('textarea[placeholder*="Ask"]', 'What was the revenue?')
    await page.click('button[title="Send message"]')

    // Wait for response - use specific selector for citation button in message area
    await expect(page.locator('.prose button:has-text("1")')).toBeVisible({ timeout: 10000 })

    // Hover over the citation
    await page.hover('.prose button:has-text("1")')

    // Tooltip should appear with file name and excerpt (use role-based selector)
    const tooltip = page.getByRole('tooltip')
    await expect(tooltip.first()).toBeVisible()
    await expect(tooltip.first().locator('text=quarterly_report.pdf')).toBeVisible()
    await expect(tooltip.first().locator('text=Page 3')).toBeVisible()
    await expect(tooltip.first().locator('text=Q4 revenue reached')).toBeVisible()
  })

  test('citation click opens Drive', async ({ page, context }) => {
    // Set up mocks
    await page.route('**/api/folders/*/chat', async (route) => {
      const sseResponse = [
        'data: {"token":"See source [1] for details."}\n\n',
        `data: {"done":true,"citations":{"1":${JSON.stringify(mockCitation)}},"searched_files":["quarterly_report.pdf"],"conversation_id":"conv-123"}\n\n`,
      ].join('')

      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: sseResponse,
      })
    })

    // Navigate to chat page
    await page.goto('/chat/test-folder-id')

    // Type and send a question
    await page.fill('textarea[placeholder*="Ask"]', 'Show me the source')
    await page.click('button[title="Send message"]')

    // Wait for response with citation - use specific selector
    await expect(page.locator('.prose button:has-text("1")')).toBeVisible({ timeout: 10000 })

    // Listen for new tab/popup
    const [newPage] = await Promise.all([
      context.waitForEvent('page'),
      page.click('.prose button:has-text("1")'),
    ])

    // New tab should open with Google Drive URL
    expect(newPage.url()).toContain('drive.google.com')
  })
})
