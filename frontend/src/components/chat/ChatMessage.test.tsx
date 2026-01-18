import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ChatMessage } from '../chat/ChatMessage'
import type { Message, Citation } from '../../types'

describe('ChatMessage', () => {
  const mockCitation: Citation = {
    chunk_id: 'chunk-1',
    file_name: 'research-paper.pdf',
    location: 'Page 42',
    excerpt: 'This is a test excerpt from the document that provides context.',
    google_drive_url: 'https://drive.google.com/file/d/abc123/view',
  }

  const userMessage: Message = {
    id: 'msg-1',
    role: 'user',
    content: 'What does the document say about testing?',
    created_at: new Date().toISOString(),
  }

  const assistantMessage: Message = {
    id: 'msg-2',
    role: 'assistant',
    content: 'According to the document [1], testing is important.',
    citations: { '1': mockCitation },
    created_at: new Date().toISOString(),
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('User Message', () => {
    it('should render user message content', () => {
      render(<ChatMessage message={userMessage} />)

      expect(screen.getByText('What does the document say about testing?')).toBeInTheDocument()
    })

    it('should display user styling', () => {
      render(<ChatMessage message={userMessage} />)

      // User messages are right-aligned bubbles with bg-muted
      const article = screen.getByLabelText('Your message')
      expect(article).toHaveClass('justify-end')
      const bubble = screen.getByText('What does the document say about testing?').closest('div')
      expect(bubble).toHaveClass('bg-muted')
    })

    it('should not show copy button for user messages', () => {
      render(<ChatMessage message={userMessage} />)

      // User messages don't have the copy button
      expect(screen.queryByTitle('Copy response')).not.toBeInTheDocument()
    })
  })

  describe('Assistant Message', () => {
    it('should render assistant message content', () => {
      render(<ChatMessage message={assistantMessage} />)

      expect(screen.getByText(/According to the document/)).toBeInTheDocument()
      expect(screen.getByText(/testing is important/)).toBeInTheDocument()
    })

    it('should display assistant styling', () => {
      render(<ChatMessage message={assistantMessage} />)

      // Assistant messages are left-aligned with group class for hover effects
      const article = screen.getByLabelText('Assistant response')
      expect(article).toHaveClass('group')
    })

    it('should show copy button for assistant messages', () => {
      render(<ChatMessage message={assistantMessage} />)

      expect(screen.getByTitle('Copy response')).toBeInTheDocument()
    })

    it('should show check icon after copy button is clicked', async () => {
      const user = userEvent.setup()
      render(<ChatMessage message={assistantMessage} />)

      const copyButton = screen.getByTitle('Copy response')

      // Before click, should show copy icon (not check icon)
      expect(copyButton.querySelector('.lucide-copy')).toBeInTheDocument()
      expect(copyButton.querySelector('.lucide-check')).not.toBeInTheDocument()

      await user.click(copyButton)

      // After click, the handleCopy function runs which calls navigator.clipboard.writeText
      // and sets copied state to true, showing the check icon
      await waitFor(() => {
        expect(copyButton.querySelector('.lucide-check')).toBeInTheDocument()
      })
    })
  })

  describe('Citation Rendering', () => {
    it('should render citation marker with file name in aria-label', () => {
      render(<ChatMessage message={assistantMessage} />)

      // Citation button shows icon only; file name is in aria-label for accessibility
      const citationButton = screen.getByRole('button', { name: /Source: research-paper.pdf/ })
      expect(citationButton).toBeInTheDocument()
      expect(citationButton.querySelector('.lucide-file-text')).toBeInTheDocument()
    })

    it('should render multiple citations with file names', () => {
      const messageWithMultipleCitations: Message = {
        id: 'msg-3',
        role: 'assistant',
        content: 'Point A [1] and point B [2] are discussed.',
        citations: {
          '1': mockCitation,
          '2': { ...mockCitation, chunk_id: 'chunk-2', file_name: 'another-doc.pdf' },
        },
        created_at: new Date().toISOString(),
      }

      render(<ChatMessage message={messageWithMultipleCitations} />)

      expect(screen.getByRole('button', { name: /Source: research-paper.pdf/ })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Source: another-doc.pdf/ })).toBeInTheDocument()
    })

    it('should call onCitationClick when citation is clicked', async () => {
      const user = userEvent.setup()
      const onCitationClick = vi.fn()

      render(<ChatMessage message={assistantMessage} onCitationClick={onCitationClick} />)

      const citationButton = screen.getByRole('button', { name: /Source: research-paper.pdf/ })
      await user.click(citationButton)

      expect(onCitationClick).toHaveBeenCalledWith(mockCitation)
    })

    it('should render citation marker even without citation data', () => {
      const messageWithMissingCitation: Message = {
        id: 'msg-4',
        role: 'assistant',
        content: 'Reference [1] has data but [2] does not.',
        citations: { '1': mockCitation },
        created_at: new Date().toISOString(),
      }

      render(<ChatMessage message={messageWithMissingCitation} />)

      // Citation [1] should be a button with accessible label showing file name
      expect(screen.getByRole('button', { name: /Source: research-paper.pdf/ })).toBeInTheDocument()

      // Citation [2] should be rendered as plain text since no citation data
      expect(screen.getByText(/\[2\]/)).toBeInTheDocument()
    })

    it('should handle long file names in aria-label', () => {
      const messageWithLongFileName: Message = {
        id: 'msg-5',
        role: 'assistant',
        content: 'See reference [1] for details.',
        citations: {
          '1': { ...mockCitation, file_name: 'this-is-a-very-long-file-name.pdf' },
        },
        created_at: new Date().toISOString(),
      }

      render(<ChatMessage message={messageWithLongFileName} />)

      // Full file name should be in aria-label; button displays icon only
      const citationButton = screen.getByRole('button', {
        name: /Source: this-is-a-very-long-file-name.pdf/,
      })
      expect(citationButton).toBeInTheDocument()
      expect(citationButton.querySelector('.lucide-file-text')).toBeInTheDocument()
    })
  })

  describe('Message without citations', () => {
    it('should render message without citations normally', () => {
      const simpleMessage: Message = {
        id: 'msg-5',
        role: 'assistant',
        content: 'This is a simple response without any citations.',
        created_at: new Date().toISOString(),
      }

      render(<ChatMessage message={simpleMessage} />)

      expect(screen.getByText('This is a simple response without any citations.')).toBeInTheDocument()
    })

    it('should handle empty citations object', () => {
      const messageWithEmptyCitations: Message = {
        id: 'msg-6',
        role: 'assistant',
        content: 'Response with empty citations.',
        citations: {},
        created_at: new Date().toISOString(),
      }

      render(<ChatMessage message={messageWithEmptyCitations} />)

      expect(screen.getByText('Response with empty citations.')).toBeInTheDocument()
    })
  })
})
