'use client'

import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface CardProps {
  children: React.ReactNode
  className?: string
  hover?: boolean
  onClick?: () => void
  accent?: 'indigo' | 'violet' | 'success' | 'warning' | 'danger' | 'none'
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

const accentStyles: Record<string, string> = {
  none: '',
  indigo: 'border-t-2 border-t-indigo-500',
  violet: 'border-t-2 border-t-violet-500',
  success: 'border-t-2 border-t-emerald-500',
  warning: 'border-t-2 border-t-amber-500',
  danger: 'border-t-2 border-t-red-500',
}

const paddingStyles: Record<string, string> = {
  none: 'p-0',
  sm: 'p-4',
  md: 'p-5',
  lg: 'p-6',
}

export function Card({
  children,
  className,
  hover = false,
  onClick,
  accent = 'none',
  padding = 'md',
}: CardProps) {
  if (hover || onClick) {
    return (
      <motion.div
        whileHover={{ y: -2, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
        transition={{ duration: 0.15 }}
        onClick={onClick}
        role={onClick ? 'button' : undefined}
        tabIndex={onClick ? 0 : undefined}
        onKeyDown={
          onClick
            ? (e) => e.key === 'Enter' && onClick()
            : undefined
        }
        className={cn(
          'bg-[#16162A] border border-[#1E1E35] rounded-xl',
          'transition-colors duration-150',
          onClick && 'cursor-pointer',
          accentStyles[accent],
          paddingStyles[padding],
          className
        )}
      >
        {children}
      </motion.div>
    )
  }

  return (
    <div
      className={cn(
        'bg-[#16162A] border border-[#1E1E35] rounded-xl',
        accentStyles[accent],
        paddingStyles[padding],
        className
      )}
    >
      {children}
    </div>
  )
}

export function CardHeader({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('flex items-center justify-between mb-4', className)}>
      {children}
    </div>
  )
}

export function CardTitle({
  children,
  className,
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <h3 className={cn('text-sm font-semibold text-[#F1F1F5]', className)}>
      {children}
    </h3>
  )
}