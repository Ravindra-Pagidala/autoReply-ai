'use client'

import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface ToggleProps {
  checked: boolean
  onChange: (checked: boolean) => void
  label?: string
  description?: string
  disabled?: boolean
  size?: 'sm' | 'md'
}

export function Toggle({
  checked,
  onChange,
  label,
  description,
  disabled = false,
  size = 'md',
}: ToggleProps) {
  const trackSize = size === 'sm'
    ? 'w-8 h-4'
    : 'w-10 h-6'
  const thumbSize = size === 'sm'
    ? 'w-3 h-3'
    : 'w-4 h-4'
  const thumbTranslate = size === 'sm'
    ? checked ? 14 : 0
    : checked ? 16 : 0

  return (
    <label
      className={cn(
        'flex items-start gap-3',
        disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'
      )}
    >
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        disabled={disabled}
        onClick={() => !disabled && onChange(!checked)}
        className={cn(
          'relative flex-shrink-0 rounded-full transition-colors duration-200 outline-none mt-0.5',
          'focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2',
          'focus-visible:ring-offset-[#0F0F1A]',
          trackSize,
          checked ? 'bg-indigo-500' : 'bg-[#2A2A45]'
        )}
      >
      <motion.span
        className={cn(
          'absolute left-[2px] top-1/2 -translate-y-1/2 rounded-full bg-white shadow-sm',
          thumbSize
        )}
        animate={{ x: thumbTranslate }}
        transition={{
          type: 'spring',
          stiffness: 400,
          damping: 30
        }}
      />
      </button>

      {(label || description) && (
        <div className="flex flex-col">
          {label && (
            <span className="text-sm font-medium text-[#F1F1F5]">{label}</span>
          )}
          {description && (
            <span className="text-xs text-[#64748B] mt-0.5">{description}</span>
          )}
        </div>
      )}
    </label>
  )
}