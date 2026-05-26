import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date): string {
  const d = new Date(date)
  return new Intl.DateTimeFormat('en-IN', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
  }).format(d)
}

export function formatTime(date: string | Date): string {
  const d = new Date(date)
  return new Intl.DateTimeFormat('en-IN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }).format(d)
}

export function formatRelativeTime(date: string | Date): string {
  const d = new Date(date)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()
  const diffSecs = Math.floor(diffMs / 1000)
  const diffMins = Math.floor(diffSecs / 60)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffSecs < 60) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return formatDate(date)
}

export function formatMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str
  return str.slice(0, length) + '...'
}

export function getInitials(name: string): string {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

export function getChannelColor(channel: string): string {
  switch (channel.toLowerCase()) {
    case 'whatsapp': return '#25D366'
    case 'voice': return '#3B82F6'
    case 'email': return '#8B5CF6'
    default: return '#94A3B8'
  }
}

export function getChannelLabel(channel: string): string {
  switch (channel.toLowerCase()) {
    case 'whatsapp': return 'WhatsApp'
    case 'voice': return 'Voice'
    case 'email': return 'Email'
    default: return channel
  }
}

export function getStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case 'new': return '#6366F1'
    case 'follow_up': return '#F59E0B'
    case 'resolved': return '#10B981'
    case 'lost': return '#EF4444'
    case 'open': return '#EF4444'
    case 'assigned': return '#F59E0B'
    case 'ai_handled': return '#10B981'
    case 'escalated': return '#EF4444'
    default: return '#94A3B8'
  }
}

export function formatNumber(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`
  return n.toString()
}