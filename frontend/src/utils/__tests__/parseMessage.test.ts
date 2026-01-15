import { describe, it, expect } from 'vitest'
import { parseMessageContent, extractCitationNumbers } from '../parseMessage'
import type { Citation } from '../../types'

describe('parseMessageContent', () => {
  const mockCitation: Citation = {
    chunk_id: 'chunk-1',
    file_name: 'test-doc.pdf',
    location: 'Page 5',
    excerpt: 'This is a test excerpt from the document.',
    google_drive_url: 'https://drive.google.com/file/d/123/view',
  }

  it('should return empty array for empty content', () => {
    expect(parseMessageContent('')).toEqual([])
  })

  it('should return single text part for content without citations', () => {
    const content = 'This is a simple message without citations.'
    const result = parseMessageContent(content)

    expect(result).toHaveLength(1)
    expect(result[0]).toEqual({
      type: 'text',
      content: 'This is a simple message without citations.',
    })
  })

  it('should parse text with single citation', () => {
    const content = 'According to the document [1], this is true.'
    const citations = { '1': mockCitation }
    const result = parseMessageContent(content, citations)

    expect(result).toHaveLength(3)
    expect(result[0]).toEqual({
      type: 'text',
      content: 'According to the document ',
    })
    expect(result[1]).toEqual({
      type: 'citation',
      content: '[1]',
      citationKey: '1',
      citation: mockCitation,
    })
    expect(result[2]).toEqual({
      type: 'text',
      content: ', this is true.',
    })
  })

  it('should parse text with multiple citations', () => {
    const content = 'Point A [1] and point B [2] are both valid.'
    const citations = {
      '1': { ...mockCitation, chunk_id: 'chunk-1' },
      '2': { ...mockCitation, chunk_id: 'chunk-2', file_name: 'other-doc.pdf' },
    }
    const result = parseMessageContent(content, citations)

    expect(result).toHaveLength(5)
    expect(result[0].type).toBe('text')
    expect(result[1].type).toBe('citation')
    expect(result[1].citationKey).toBe('1')
    expect(result[2].type).toBe('text')
    expect(result[3].type).toBe('citation')
    expect(result[3].citationKey).toBe('2')
    expect(result[4].type).toBe('text')
  })

  it('should handle citation at start of message', () => {
    const content = '[1] This starts with a citation.'
    const citations = { '1': mockCitation }
    const result = parseMessageContent(content, citations)

    expect(result).toHaveLength(2)
    expect(result[0].type).toBe('citation')
    expect(result[1].type).toBe('text')
  })

  it('should handle citation at end of message', () => {
    const content = 'This ends with a citation [1]'
    const citations = { '1': mockCitation }
    const result = parseMessageContent(content, citations)

    expect(result).toHaveLength(2)
    expect(result[0].type).toBe('text')
    expect(result[1].type).toBe('citation')
  })

  it('should handle missing citation data gracefully', () => {
    const content = 'Reference [1] exists but [2] does not.'
    const citations = { '1': mockCitation }
    const result = parseMessageContent(content, citations)

    expect(result).toHaveLength(5)

    // First citation has data
    expect(result[1].citation).toEqual(mockCitation)

    // Second citation has no data
    expect(result[3].citation).toBeUndefined()
    expect(result[3].citationKey).toBe('2')
  })

  it('should handle consecutive citations', () => {
    const content = 'See references [1][2][3] for more info.'
    const result = parseMessageContent(content)

    expect(result).toHaveLength(5)
    expect(result[0].type).toBe('text')
    expect(result[0].content).toBe('See references ')
    expect(result[1].type).toBe('citation')
    expect(result[1].citationKey).toBe('1')
    expect(result[2].type).toBe('citation')
    expect(result[2].citationKey).toBe('2')
    expect(result[3].type).toBe('citation')
    expect(result[3].citationKey).toBe('3')
    expect(result[4].type).toBe('text')
  })

  it('should not match non-numeric brackets', () => {
    const content = 'This [text] is not a citation, but [1] is.'
    const citations = { '1': mockCitation }
    const result = parseMessageContent(content, citations)

    expect(result).toHaveLength(3)
    expect(result[0].content).toBe('This [text] is not a citation, but ')
    expect(result[1].type).toBe('citation')
  })

  it('should handle undefined citations parameter', () => {
    const content = 'Message with [1] citation but no data.'
    const result = parseMessageContent(content)

    expect(result).toHaveLength(3)
    expect(result[1].citation).toBeUndefined()
  })
})

describe('extractCitationNumbers', () => {
  it('should return empty array for content without citations', () => {
    expect(extractCitationNumbers('No citations here.')).toEqual([])
  })

  it('should extract single citation number', () => {
    expect(extractCitationNumbers('Text with [1] citation.')).toEqual(['1'])
  })

  it('should extract multiple citation numbers in order', () => {
    expect(extractCitationNumbers('Citations [1], [3], [2] here.')).toEqual(['1', '3', '2'])
  })

  it('should extract consecutive citation numbers', () => {
    expect(extractCitationNumbers('See [1][2][3].')).toEqual(['1', '2', '3'])
  })

  it('should handle large citation numbers', () => {
    expect(extractCitationNumbers('Reference [123] is valid.')).toEqual(['123'])
  })

  it('should ignore non-numeric brackets', () => {
    expect(extractCitationNumbers('This [text] is ignored, [1] is not.')).toEqual(['1'])
  })
})
