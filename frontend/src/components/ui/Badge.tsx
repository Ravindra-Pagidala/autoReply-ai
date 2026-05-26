import { cn } from '@/lib/utils'

type BadgeVariant = 'indigo' | 'violet' | 'success' | 'warning' | 'danger' | 'default' | 'whatsapp' | 'voice' | 'email'

interface BadgeProps {
  children: React.ReactNode
  variant?: BadgeVariant
  size?: 'sm' | 'md'
  dot?: boolean
  className?: string
}

const variantStyles: Record<BadgeVariant, string> = {
  indigo:    'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20',
  violet:    'bg-violet-500/10 text-violet-400 border border-violet-500/20',
  success:   'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20',
  warning:   'bg-amber-500/10 text-amber-400 border border-amber-500/20',
  danger:    'bg-red-500/10 text-red-400 border border-red-500/20',
  default:   'bg-[#1E1E35] text-[#94A3B8] border border-[#2A2A45]',
  whatsapp:  'bg-[#25D366]/10 text-[#25D366] border border-[#25D366]/20',
  voice:     'bg-blue-500/10 text-blue-400 border border-blue-500/20',
  email:     'bg-violet-500/10 text-violet-400 border border-violet-500/20',
}

const dotColors: Record<BadgeVariant, string> = {
  indigo:   'bg-indigo-400',
  violet:   'bg-violet-400',
  success:  'bg-emerald-400',
  warning:  'bg-amber-400',
  danger:   'bg-red-400',
  default:  'bg-[#94A3B8]',
  whatsapp: 'bg-[#25D366]',
  voice:    'bg-blue-400',
  email:    'bg-violet-400',
}

const sizeStyles: Record<string, string> = {
  sm: 'text-[10px] px-1.5 py-0.5 gap-1',
  md: 'text-xs px-2 py-0.5 gap-1.5',
}

export function Badge({
  children,
  variant = 'default',
  size = 'md',
  dot = false,
  className,
}: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full font-medium',
        variantStyles[variant],
        sizeStyles[size],
        className
      )}
    >
      {dot && (
        <span
          className={cn('rounded-full flex-shrink-0', dotColors[variant], size === 'sm' ? 'w-1 h-1' : 'w-1.5 h-1.5')}
          aria-hidden="true"
        />
      )}
      {children}
    </span>
  )
}

export function ChannelBadge({ channel }: { channel: string }) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    whatsapp: { variant: 'whatsapp', label: 'WhatsApp' },
    voice:    { variant: 'voice',    label: 'Voice' },
    email:    { variant: 'email',    label: 'Email' },
  }
  const config = map[channel.toLowerCase()] ?? { variant: 'default', label: channel }
  return <Badge variant={config.variant} dot>{config.label}</Badge>
}

export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { variant: BadgeVariant; label: string }> = {
    new:        { variant: 'indigo',  label: 'New' },
    follow_up:  { variant: 'warning', label: 'Follow up' },
    resolved:   { variant: 'success', label: 'Resolved' },
    lost:       { variant: 'danger',  label: 'Lost' },
    open:       { variant: 'danger',  label: 'Open' },
    assigned:   { variant: 'warning', label: 'Assigned' },
    ai_handled: { variant: 'success', label: 'AI Handled' },
    escalated:  { variant: 'danger',  label: 'Escalated' },
    pending:    { variant: 'warning', label: 'Pending' },
    accepted:   { variant: 'success', label: 'Accepted' },
    trained:    { variant: 'success', label: 'Trained' },
    processing: { variant: 'warning', label: 'Processing' },
    failed:     { variant: 'danger',  label: 'Failed' },
  }
  const config = map[status.toLowerCase()] ?? { variant: 'default', label: status }
  return <Badge variant={config.variant} dot>{config.label}</Badge>
}