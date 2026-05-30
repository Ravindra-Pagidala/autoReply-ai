'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard, MessageSquare, Users, AlertTriangle,
  BookOpen, Settings, ChevronLeft, ChevronRight,
  Zap, CalendarDays, Megaphone,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useUIStore } from '@/store/ui.store'
import { useAuthStore } from '@/store/auth.store'
import { getInitials } from '@/lib/utils'

const navItems = [
  { href: '/dashboard', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/dashboard/inbox', icon: MessageSquare, label: 'Inbox' },
  { href: '/dashboard/leads', icon: Users, label: 'Leads' },
  { href: '/dashboard/appointments', icon: CalendarDays, label: 'Appointments' },
  { href: '/dashboard/broadcast', icon: Megaphone, label: 'Broadcast' },
  { href: '/dashboard/escalations', icon: AlertTriangle, label: 'Escalations' },
  { href: '/dashboard/knowledge', icon: BookOpen, label: 'Knowledge Base' },
  { href: '/dashboard/settings', icon: Settings, label: 'Settings' },
]

export function Sidebar() {
  const pathname = usePathname()
  const { sidebarCollapsed, toggleSidebar } = useUIStore()
  const { user, profile } = useAuthStore()

  return (
    <motion.aside
      animate={{
        width: sidebarCollapsed ? 56 : 240
      }}
      style={{
        willChange: 'width'
      }}
      transition={{ duration: 0.2, ease: 'easeOut' }}
      className="fixed left-0 top-0 h-full z-40 flex flex-col bg-[#16162A] border-r border-[#1E1E35] overflow-hidden"
    >
      {/* Logo */}
      <div className="flex items-center h-14 px-3 border-b border-[#1E1E35] flex-shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg bg-indigo-500 flex items-center justify-center flex-shrink-0">
            <Zap size={16} className="text-white" />
          </div>
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.span
                initial={{ opacity: 0, width: 0 }}
                animate={{ opacity: 1, width: 'auto' }}
                exit={{ opacity: 0, width: 0 }}
                transition={{ duration: 0.15 }}
                className="text-sm font-semibold text-[#F1F1F5] whitespace-nowrap overflow-hidden"
              >
                AutoReply AI
              </motion.span>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto" aria-label="Main navigation">
        {navItems.map(({ href, icon: Icon, label }) => {
          const isActive = pathname === href || (href !== '/dashboard' && pathname.startsWith(href))
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 h-9 px-2 rounded-lg',
                'transition-all duration-150 outline-none group relative',
                'focus-visible:ring-2 focus-visible:ring-indigo-500',
                isActive
                  ? 'bg-indigo-500/10 text-indigo-400'
                  : 'text-[#64748B] hover:bg-[#1E1E35] hover:text-[#F1F1F5]'
              )}
              aria-current={isActive ? 'page' : undefined}
              title={sidebarCollapsed ? label : undefined}
            >
              {isActive && (
                <motion.div
                  layoutId="sidebar-active"
                  className="absolute left-0 top-1 bottom-1 w-0.5 bg-indigo-500 rounded-full"
                />
              )}
              <Icon size={16} className="flex-shrink-0" aria-hidden="true" />
              <AnimatePresence>
                {!sidebarCollapsed && (
                  <motion.span
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.1 }}
                    className="text-sm font-medium whitespace-nowrap overflow-hidden"
                  >
                    {label}
                  </motion.span>
                )}
              </AnimatePresence>
            </Link>
          )
        })}
      </nav>

      {/* User + collapse */}
      <div className="border-t border-[#1E1E35] p-2 space-y-1 flex-shrink-0">
        {/* User avatar */}
        <div className="flex items-center gap-3 px-2 py-2 rounded-lg">
          <div className="w-7 h-7 rounded-full bg-indigo-500/20 flex items-center justify-center flex-shrink-0">
            <span className="text-[10px] font-semibold text-indigo-400">
              {getInitials(profile?.business_name || user?.email || 'U')}
            </span>
          </div>
          <AnimatePresence>
            {!sidebarCollapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="min-w-0"
              >
                <p className="text-xs font-medium text-[#F1F1F5] truncate">
                  {profile?.business_name || 'My Business'}
                </p>
                <p className="text-[10px] text-[#64748B] truncate">{user?.email}</p>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Collapse toggle */}
        <button
          onClick={toggleSidebar}
          className={cn(
            'w-full flex items-center gap-3 h-8 px-2 rounded-lg',
            'text-[#64748B] hover:bg-[#1E1E35] hover:text-[#F1F1F5]',
            'transition-colors duration-150 outline-none',
            'focus-visible:ring-2 focus-visible:ring-indigo-500'
          )}
          aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {sidebarCollapsed
            ? <ChevronRight size={14} aria-hidden="true" />
            : <><ChevronLeft size={14} aria-hidden="true" />
              <span className="text-xs">Collapse</span></>
          }
        </button>
      </div>
    </motion.aside>
  )
}