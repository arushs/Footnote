import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MessageInput } from './MessageInput'

describe('MessageInput', () => {
  describe('Rendering', () => {
    it('should render textarea with default placeholder', () => {
      render(<MessageInput onSend={vi.fn()} />)

      expect(screen.getByRole('textbox')).toHaveAttribute(
        'placeholder',
        'Ask about your files...'
      )
    })

    it('should render with custom placeholder', () => {
      render(<MessageInput onSend={vi.fn()} placeholder="Custom placeholder" />)

      expect(screen.getByRole('textbox')).toHaveAttribute(
        'placeholder',
        'Custom placeholder'
      )
    })

    it('should render send button when not loading', () => {
      render(<MessageInput onSend={vi.fn()} />)

      expect(screen.getByRole('button', { name: /send message/i })).toBeInTheDocument()
    })

    it('should render stop button when loading', () => {
      render(<MessageInput onSend={vi.fn()} isLoading={true} />)

      expect(screen.getByRole('button', { name: /stop generation/i })).toBeInTheDocument()
    })

    it('should show helper text', () => {
      render(<MessageInput onSend={vi.fn()} />)

      expect(screen.getByText(/press enter to send/i)).toBeInTheDocument()
    })
  })

  describe('Input behavior', () => {
    it('should update value when typing', async () => {
      const user = userEvent.setup()
      render(<MessageInput onSend={vi.fn()} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Hello world')

      expect(textarea).toHaveValue('Hello world')
    })

    it('should be disabled when disabled prop is true', () => {
      render(<MessageInput onSend={vi.fn()} disabled={true} />)

      expect(screen.getByRole('textbox')).toBeDisabled()
    })
  })

  describe('Send functionality', () => {
    it('should call onSend with trimmed message on form submit', async () => {
      const user = userEvent.setup()
      const onSend = vi.fn()
      render(<MessageInput onSend={onSend} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, '  Hello world  ')
      await user.click(screen.getByRole('button', { name: /send message/i }))

      expect(onSend).toHaveBeenCalledWith('Hello world')
    })

    it('should clear input after sending', async () => {
      const user = userEvent.setup()
      render(<MessageInput onSend={vi.fn()} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Hello world')
      await user.click(screen.getByRole('button', { name: /send message/i }))

      expect(textarea).toHaveValue('')
    })

    it('should not send empty messages', async () => {
      const user = userEvent.setup()
      const onSend = vi.fn()
      render(<MessageInput onSend={onSend} />)

      await user.click(screen.getByRole('button', { name: /send message/i }))

      expect(onSend).not.toHaveBeenCalled()
    })

    it('should not send whitespace-only messages', async () => {
      const user = userEvent.setup()
      const onSend = vi.fn()
      render(<MessageInput onSend={onSend} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, '   ')
      await user.click(screen.getByRole('button', { name: /send message/i }))

      expect(onSend).not.toHaveBeenCalled()
    })

    it('should not send when disabled', async () => {
      const user = userEvent.setup()
      const onSend = vi.fn()
      render(<MessageInput onSend={onSend} disabled={true} />)

      const textarea = screen.getByRole('textbox')
      // Can't type in disabled textarea, so we test the button is disabled
      expect(screen.getByRole('button', { name: /send message/i })).toBeDisabled()
    })

    it('should not send when loading', async () => {
      const user = userEvent.setup()
      const onSend = vi.fn()
      render(<MessageInput onSend={onSend} isLoading={true} />)

      // Stop button should be shown instead of send
      expect(screen.queryByRole('button', { name: /send message/i })).not.toBeInTheDocument()
    })
  })

  describe('Keyboard shortcuts', () => {
    it('should send message on Enter key', async () => {
      const user = userEvent.setup()
      const onSend = vi.fn()
      render(<MessageInput onSend={onSend} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Hello world')
      await user.keyboard('{Enter}')

      expect(onSend).toHaveBeenCalledWith('Hello world')
    })

    it('should not send on Shift+Enter (new line)', async () => {
      const user = userEvent.setup()
      const onSend = vi.fn()
      render(<MessageInput onSend={onSend} />)

      const textarea = screen.getByRole('textbox')
      await user.type(textarea, 'Hello')
      await user.keyboard('{Shift>}{Enter}{/Shift}')
      await user.type(textarea, 'World')

      expect(onSend).not.toHaveBeenCalled()
      expect(textarea).toHaveValue('Hello\nWorld')
    })
  })

  describe('Stop functionality', () => {
    it('should call onStop when stop button is clicked', async () => {
      const user = userEvent.setup()
      const onStop = vi.fn()
      render(<MessageInput onSend={vi.fn()} onStop={onStop} isLoading={true} />)

      await user.click(screen.getByRole('button', { name: /stop generation/i }))

      expect(onStop).toHaveBeenCalled()
    })
  })

  describe('Send button state', () => {
    it('should disable send button when input is empty', () => {
      render(<MessageInput onSend={vi.fn()} />)

      expect(screen.getByRole('button', { name: /send message/i })).toBeDisabled()
    })

    it('should enable send button when input has content', async () => {
      const user = userEvent.setup()
      render(<MessageInput onSend={vi.fn()} />)

      await user.type(screen.getByRole('textbox'), 'Hello')

      expect(screen.getByRole('button', { name: /send message/i })).not.toBeDisabled()
    })

    it('should disable send button when disabled prop is true', async () => {
      const user = userEvent.setup()
      render(<MessageInput onSend={vi.fn()} disabled={true} />)

      expect(screen.getByRole('button', { name: /send message/i })).toBeDisabled()
    })
  })
})
