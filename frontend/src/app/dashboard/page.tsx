'use client'

import { useQuery } from '@tanstack/react-query'
import { MessageSquare, Users, AlertTriangle, Zap, Phone, Mail } from 'lucide-react'
import { motion } from 'framer-motion'
import { get } from '@/lib/api'
import { useAuthStore } from '@/store/auth.store'
import { StatsCard } from '@/components/dashboard/StatsCard'
import { LiveFeed } from '@/components/dashboard/LiveFeed'
import { formatMs } from '@/lib/utils'
import { staggerContainer, staggerItem } from '@/lib/animations'
import type { DashboardStats } from '@/types'

export default function DashboardPage() {
  const { profile } = useAuthStore()

  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: () => get<DashboardStats>('/dashboard/stats'),
    refetchInterval: 30000,
  })

  const hour = new Date().getHours()
  const greeting = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening'

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Greeting */}
      <motion.div
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2 }}
        className="mb-6"
      >
        <h2 className="text-lg font-semibold text-[#F1F1F5]">
          {greeting}, {profile?.business_name ?? 'there'} 👋
        </h2>
        <p className="text-xs text-[#64748B] mt-0.5">
          Here&apos;s what&apos;s happening with your AI bot today
        </p>
      </motion.div>

      {/* Stats grid */}
      <motion.div
        variants={staggerContainer}
        initial="initial"
        animate="animate"
        className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6"
      >
        <motion.div variants={staggerItem}>
          <StatsCard
            title="Messages Today"
            value={stats?.messages_today ?? 0}
            icon={<MessageSquare size={16} />}
            accent="indigo"
            loading={isLoading}
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <StatsCard
            title="Leads Captured"
            value={stats?.leads_today ?? 0}
            icon={<Users size={16} />}
            accent="violet"
            loading={isLoading}
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <StatsCard
            title="Open Escalations"
            value={stats?.escalations_open ?? 0}
            icon={<AlertTriangle size={16} />}
            accent={stats?.escalations_open ? 'danger' : 'success'}
            loading={isLoading}
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <StatsCard
            title="Avg Response"
            value={stats ? formatMs(stats.avg_response_ms) : '—'}
            icon={<Zap size={16} />}
            accent="success"
            loading={isLoading}
          />
        </motion.div>
      </motion.div>

      {/* Secondary stats */}
      <motion.div
        variants={staggerContainer}
        initial="initial"
        animate="animate"
        className="grid grid-cols-3 gap-4 mb-6"
      >
        <motion.div variants={staggerItem}>
          <StatsCard
            title="Voice Calls Today"
            value={stats?.calls_today ?? 0}
            icon={<Phone size={16} />}
            accent="indigo"
            loading={isLoading}
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <StatsCard
            title="Emails Today"
            value={stats?.emails_today ?? 0}
            icon={<Mail size={16} />}
            accent="violet"
            loading={isLoading}
          />
        </motion.div>
        <motion.div variants={staggerItem}>
          <StatsCard
            title="Total Leads"
            value={stats?.total_leads ?? 0}
            icon={<Users size={16} />}
            accent="success"
            loading={isLoading}
          />
        </motion.div>
      </motion.div>

      {/* Live feed */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, delay: 0.15 }}
      >
        <LiveFeed />
      </motion.div>
    </div>
  )
}