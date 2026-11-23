import { useLayoutEffect, useRef, useState } from 'react'
import type { SupportMessage } from '@/hooks/use-support'
import { getIntlLocale } from '@/i18n/core'

export interface Conversation {
  items: SupportMessage[]
  fetchedThrough: number
  hasOlder: boolean
}

export const conversationKey = (ticketId: string) => ['support', 'messages', ticketId]

export function mergeMessages(previous: SupportMessage[], next: SupportMessage[]) {
  const merged = new Map(previous.map((message) => [message.seq, message]))
  next.forEach((message) => merged.set(message.seq, message))
  return [...merged.values()].sort((a, b) => a.seq - b.seq)
}

/** A short chat title from the first message: its first line, at most 60 characters. */
export function subjectFrom(body: string) {
  const line = body.trim().split('\n')[0]?.replace(/\s+/g, ' ').trim() ?? ''
  return line.length > 60 ? `${line.slice(0, 59).trimEnd()}…` : line
}

export function chatTime(iso: string) {
  const date = new Date(iso)
  const today = new Date().toDateString() === date.toDateString()
  return new Intl.DateTimeFormat(getIntlLocale(), {
    ...(today ? {} : { day: 'numeric', month: 'short' }),
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

/** Keeps the log pinned to its end while new content arrives, unless the reader scrolled up. */
export function useChatScroll() {
  const scrollRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const stick = useRef(true)
  const [atBottom, setAtBottom] = useState(true)
  useLayoutEffect(() => {
    const outer = scrollRef.current
    const inner = contentRef.current
    if (!outer || !inner) return
    outer.scrollTop = outer.scrollHeight
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => {
      if (stick.current) outer.scrollTop = outer.scrollHeight
    })
    observer.observe(inner)
    return () => observer.disconnect()
  }, [])
  const onScroll = () => {
    const element = scrollRef.current
    if (!element) return
    stick.current = element.scrollHeight - element.scrollTop - element.clientHeight < 80
    setAtBottom(stick.current)
  }
  const scrollToBottom = () => {
    const element = scrollRef.current
    stick.current = true
    setAtBottom(true)
    element?.scrollTo({ top: element.scrollHeight, behavior: 'smooth' })
  }
  const keepPosition = async (work: () => Promise<void>) => {
    const element = scrollRef.current
    const height = element?.scrollHeight ?? 0
    stick.current = false
    await work()
    requestAnimationFrame(() => {
      if (element) element.scrollTop += element.scrollHeight - height
    })
  }
  return { scrollRef, contentRef, stick, atBottom, onScroll, scrollToBottom, keepPosition }
}
