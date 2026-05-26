'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { useQuery } from '@tanstack/react-query'
import { MessageSquare, Phone, Mail, AlertTriangle } from 'lucide-react'
import { get } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import { ChannelBadge, StatusBadge } from '@/components/ui/Badge'
import { staggerItem } from '@/lib/animations'
import type { PaginatedResponse, Conversation } from '@/types'

const channelIcon = {
  whatsapp: <MessageSquare size={14} className="text-[#25D366]" />,
  voice:    <Phone size={14} className="text-blue-400" />,
  email:    <Mail size={14} className="text-violet-400" />,
}

export function LiveFeed() {
  const { data, isLoading } = useQuery({
    queryKey: ['conversations-feed'],
    queryFn: () => get<PaginatedResponse<Conversation>>('/dashboard/conversations?page_size=8'),
    refetchInterval: 10000,
  })

  const conversations = data?.data ?? []

  return (
    <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-5 py-4 border-b border-[#1E1E35]">
        <h3 className="text-sm font-semibold text-[#F1F1F5]">Live Activity</h3>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" aria-hidden="true" />
          <span className="text-xs text-emerald-400">Live</span>
        </div>
      </div>

      <div className="divide-y divide-[#1E1E35]">
        {isLoading ? (
          [...Array(5)].map((_, i) => (
            <div key={i} className="flex items-center gap-3 px-5 py-3">
              <div className="skeleton w-8 h-8 rounded-full flex-shrink-0" />
              <div className="flex-1 space-y-1.5">
                <div className="skeleton h-3 w-32 rounded" />
                <div className="skeleton h-2.5 w-48 rounded" />
              </div>
            </div>
          ))
        ) : conversations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <MessageSquare size={24} className="text-[#2A2A45]" />
            <p className="text-xs text-[#4A4A6A]">No conversations yet</p>
            <p className="text-xs text-[#4A4A6A]">Messages will appear here in real time</p>
          </div>
        ) : (
          <AnimatePresence>
            {conversations.map((conv, i) => (
              <motion.div
                key={conv.id}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.04, duration: 0.2 }}
                className="flex items-center gap-3 px-5 py-3 hover:bg-[#1E1E35]/50 transition-colors duration-150 group"
              >
                {/* Channel icon */}
                <div className="w-8 h-8 rounded-full bg-[#1E1E35] flex items-center justify-center flex-shrink-0">
                  {channelIcon[conv.channel as keyof typeof channelIcon] ?? <MessageSquare size={14} className="text-[#64748B]" />}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-xs font-medium text-[#F1F1F5] truncate">{conv.from_contact}</p>
                    <ChannelBadge channel={conv.channel} />
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <StatusBadge status={conv.escalated ? 'escalated' : conv.status} />
                    {conv.response_time_ms && (
                      <span className="text-[10px] text-[#4A4A6A]">{conv.response_time_ms}ms</span>
                    )}
                  </div>
                </div>

                {/* Time */}
                <span className="text-[10px] text-[#4A4A6A] flex-shrink-0">
                  {conv.created_at ? formatRelativeTime(conv.created_at) : '—'}
                </span>

                {/* Escalation indicator */}
                {conv.escalated && (
                  <AlertTriangle size={12} className="text-red-400 flex-shrink-0" aria-label="Escalated" />
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>
    </div>
  )
}