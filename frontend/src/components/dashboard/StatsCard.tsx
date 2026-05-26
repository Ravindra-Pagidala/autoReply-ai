'use client'

import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface StatsCardProps {
  title: string
  value: string | number
  icon: React.ReactNode
  trend?: { value: string; positive: boolean }
  accent?: 'indigo' | 'violet' | 'success' | 'warning' | 'danger'
  loading?: boolean
}

const accentMap = {
  indigo:  { bar: 'bg-indigo-500',  icon: 'bg-indigo-500/10 text-indigo-400' },
  violet:  { bar: 'bg-violet-500',  icon: 'bg-violet-500/10 text-violet-400' },
  success: { bar: 'bg-emerald-500', icon: 'bg-emerald-500/10 text-emerald-400' },
  warning: { bar: 'bg-amber-500',   icon: 'bg-amber-500/10 text-amber-400' },
  danger:  { bar: 'bg-red-500',     icon: 'bg-red-500/10 text-red-400' },
}

export function StatsCard({
  title, value, icon, trend, accent = 'indigo', loading = false,
}: StatsCardProps) {
  const colors = accentMap[accent]

  if (loading) {
    return (
      <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5">
        <div className="skeleton h-3 w-24 mb-3 rounded" />
        <div className="skeleton h-8 w-16 mb-2 rounded" />
        <div className="skeleton h-2 w-12 rounded" />
      </div>
    )
  }

  return (
    <motion.div
      whileHover={{ y: -2, boxShadow: '0 8px 32px rgba(0,0,0,0.4)' }}
      transition={{ duration: 0.15 }}
      className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5 relative overflow-hidden"
    >
      {/* Top accent bar */}
      <div className={cn('absolute top-0 left-0 right-0 h-0.5', colors.bar)} />

      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-[#64748B] font-medium">{title}</p>
          <motion.p
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="text-2xl font-bold text-[#F1F1F5] mt-1"
          >
            {value}
          </motion.p>
          {trend && (
            <p className={cn('text-xs mt-1 font-medium', trend.positive ? 'text-emerald-400' : 'text-red-400')}>
              {trend.positive ? '↑' : '↓'} {trend.value}
            </p>
          )}
        </div>
        <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0', colors.icon)}>
          {icon}
        </div>
      </div>
    </motion.div>
  )
}