import type { Citation } from '../types'

export interface ParsedPart {
  type: 'text' | 'citation'
  content: string
  citationKey?: string
  citation?: Citation
}

/**
 * Parse message content and extract citation markers.
 * Citation markers are in the format [N] where N is a number.
 */
export function parseMessageContent(
  content: string,
  citations?: Record<string, Citation>
): ParsedPart[] {
  if (!content) return []

  const citationPattern = /\[(\d+)\]/g
  const parts: ParsedPart[] = []
  let lastIndex = 0
  let match

  while ((match = citationPattern.exec(content)) !== null) {
    // Add text before the citation
    if (match.index > lastIndex) {
      parts.push({
        type: 'text',
        content: content.slice(lastIndex, match.index),
      })
    }

    const citationKey = match[1]
    const citation = citations?.[citationKey]

    parts.push({
      type: 'citation',
      content: match[0],
      citationKey,
      citation,
    })

    lastIndex = match.index + match[0].length
  }

  // Add remaining text
  if (lastIndex < content.length) {
    parts.push({
      type: 'text',
      content: content.slice(lastIndex),
    })
  }

  return parts
}

/**
 * Extract all citation numbers from a message.
 */
export function extractCitationNumbers(content: string): string[] {
  const citationPattern = /\[(\d+)\]/g
  const numbers: string[] = []
  let match

  while ((match = citationPattern.exec(content)) !== null) {
    numbers.push(match[1])
  }

  return numbers
}
