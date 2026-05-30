'use client'

import { usePathname } from 'next/navigation'
import { Bell, LogOut } from 'lucide-react'
import { motion } from 'framer-motion'
import { useUIStore } from '@/store/ui.store'
import { useAuthStore } from '@/store/auth.store'
import { supabase } from '@/lib/supabase'
import { useToast } from '@/components/ui/Toast'
import { useQuery } from '@tanstack/react-query'
import { get } from '@/lib/api'
import type { DashboardStats } from '@/types'
import { cn } from '@/lib/utils'

const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/dashboard/inbox': 'Inbox',
  '/dashboard/leads': 'Leads',
  '/dashboard/appointments': 'Appointments',
  '/dashboard/escalations': 'Escalations',
  '/dashboard/knowledge': 'Knowledge Base',
  '/dashboard/test-system': 'Test System',
  '/dashboard/settings': 'Settings',
}

export function TopBar() {
  const pathname = usePathname()
  const { sidebarCollapsed } = useUIStore()
  const { user, profile, logout } = useAuthStore()
  const toast = useToast()

  const { data: stats } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => get<DashboardStats>('/dashboard/stats'),
    refetchInterval: 30000,
  })

  const unread = stats?.unread_notifications ?? 0
  const title = pageTitles[pathname] ?? 'Dashboard'

  const handleLogout = async () => {
    await supabase.auth.signOut()
    logout()
    toast.success('Signed out successfully')
    window.location.href = '/login'
  }

  return (
    <header
      className={cn(
        'fixed top-0 right-0 z-30 h-14',
        'flex items-center justify-between',
        'px-5',
        'bg-[#12121F]/90 backdrop-blur-sm',
        'border-b border-[#1E1E35]',
        'transition-all duration-200',
        sidebarCollapsed ? 'left-[56px]' : 'left-[240px]'
      )}
>
      {/* Page title */}
      <div>
        <h1 className="text-sm font-semibold text-[#F1F1F5]">{title}</h1>
        {profile?.business_name && (
          <p className="text-[10px] text-[#64748B]">{profile.business_name}</p>
        )}
      </div>

      {/* Right actions */}
      <div className="flex items-center gap-2">
        {/* Bot status */}
        {profile && (
          <div className={cn(
            'flex items-center gap-1.5 px-3 h-7 rounded-full text-xs font-medium',
            profile.bot_active
              ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
              : 'bg-red-500/10 text-red-400 border border-red-500/20'
          )}>
            <span
              className={cn(
                'w-1.5 h-1.5 rounded-full',
                profile.bot_active ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'
              )}
              aria-hidden="true"
            />
            {profile.bot_active ? 'Bot Active' : 'Bot Paused'}
          </div>
        )}

        {/* Notifications */}
        <button
          className={cn(
            'relative w-8 h-8 rounded-lg flex items-center justify-center',
            'text-[#64748B] hover:bg-[#1E1E35] hover:text-[#F1F1F5]',
            'transition-colors duration-150 outline-none',
            'focus-visible:ring-2 focus-visible:ring-indigo-500'
          )}
          aria-label={`Notifications${unread > 0 ? `, ${unread} unread` : ''}`}
        >
          <Bell size={16} aria-hidden="true" />
          {unread > 0 && (
            <motion.span
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 rounded-full flex items-center justify-center"
            >
              <span className="text-[9px] text-white font-bold">
                {unread > 9 ? '9+' : unread}
              </span>
            </motion.span>
          )}
        </button>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className={cn(
            'w-8 h-8 rounded-lg flex items-center justify-center',
            'text-[#64748B] hover:bg-[#1E1E35] hover:text-red-400',
            'transition-colors duration-150 outline-none',
            'focus-visible:ring-2 focus-visible:ring-indigo-500'
          )}
          aria-label="Sign out"
        >
          <LogOut size={16} aria-hidden="true" />
        </button>
      </div>
    </header>
  )
}