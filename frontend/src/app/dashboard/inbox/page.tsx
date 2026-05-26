'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { MessageSquare, Phone, Mail, Bot, User, AlertTriangle } from 'lucide-react'
import { get } from '@/lib/api'
import { formatRelativeTime, truncate } from '@/lib/utils'
import { ChannelBadge, StatusBadge } from '@/components/ui/Badge'
import { ConversationSkeleton } from '@/components/ui/Skeleton'
import { fadeInUp } from '@/lib/animations'
import type { PaginatedResponse, Conversation, Message } from '@/types'

const CHANNEL_FILTERS = ['all', 'whatsapp', 'voice', 'email'] as const
type ChannelFilter = typeof CHANNEL_FILTERS[number]

const channelIcon: Record<string, React.ReactNode> = {
  whatsapp: <MessageSquare size={14} className="text-[#25D366]" />,
  voice:    <Phone size={14} className="text-blue-400" />,
  email:    <Mail size={14} className="text-violet-400" />,
}

export default function InboxPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [channelFilter, setChannelFilter] = useState<ChannelFilter>('all')

  const { data, isLoading } = useQuery({
    queryKey: ['conversations', channelFilter],
    queryFn: () =>
      get<PaginatedResponse<Conversation>>(
        `/dashboard/conversations?page_size=30${channelFilter !== 'all' ? `&channel=${channelFilter}` : ''}`
      ),
    refetchInterval: 10000,
  })

  const { data: messages, isLoading: msgsLoading } = useQuery({
    queryKey: ['messages', selectedId],
    queryFn: () =>
      get<Message[]>(`/dashboard/conversations/${selectedId}/messages`),
    enabled: !!selectedId,
  })

  const conversations = data?.data ?? []
  const selected = conversations.find((c) => c.id === selectedId)

  return (
    <div className="flex h-[calc(100vh-56px)] overflow-hidden">
      {/* Left panel — conversation list */}
      <div className="w-80 flex-shrink-0 border-r border-[#1E1E35] flex flex-col bg-[#16162A]">
        {/* Header + filters */}
        <div className="p-4 border-b border-[#1E1E35]">
          <h2 className="text-sm font-semibold text-[#F1F1F5] mb-3">Inbox</h2>
          <div className="flex gap-1.5 flex-wrap">
            {CHANNEL_FILTERS.map((f) => (
              <button
                key={f}
                onClick={() => { setChannelFilter(f); setSelectedId(null) }}
                className={`px-3 h-7 rounded-full text-xs font-medium capitalize transition-all duration-150 ${
                  channelFilter === f
                    ? 'bg-indigo-500 text-white'
                    : 'bg-[#1E1E35] text-[#64748B] hover:text-[#F1F1F5]'
                }`}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            [...Array(6)].map((_, i) => <ConversationSkeleton key={i} />)
          ) : conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 p-6">
              <MessageSquare size={28} className="text-[#2A2A45]" />
              <p className="text-xs text-[#4A4A6A] text-center">No conversations yet</p>
            </div>
          ) : (
            <AnimatePresence>
              {conversations.map((conv, i) => (
                <motion.button
                  key={conv.id}
                  initial={{ opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.03, duration: 0.15 }}
                  onClick={() => setSelectedId(conv.id)}
                  className={`w-full flex items-start gap-3 px-4 py-3 text-left transition-colors duration-150 border-b border-[#1E1E35]/50 relative ${
                    selectedId === conv.id
                      ? 'bg-indigo-500/10'
                      : 'hover:bg-[#1E1E35]/60'
                  }`}
                  aria-current={selectedId === conv.id ? 'true' : undefined}
                >
                  {selectedId === conv.id && (
                    <div className="absolute left-0 top-2 bottom-2 w-0.5 bg-indigo-500 rounded-full" />
                  )}

                  <div className="w-8 h-8 rounded-full bg-[#1E1E35] flex items-center justify-center flex-shrink-0 mt-0.5">
                    {channelIcon[conv.channel] ?? <MessageSquare size={14} className="text-[#64748B]" />}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-xs font-medium text-[#F1F1F5] truncate">{conv.from_contact}</p>
                      <span className="text-[10px] text-[#4A4A6A] flex-shrink-0">
                        {conv.created_at ? formatRelativeTime(conv.created_at) : ''}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5 mt-1">
                      <StatusBadge status={conv.escalated ? 'escalated' : conv.status} />
                      {conv.escalated && (
                        <AlertTriangle size={10} className="text-red-400" aria-label="Escalated" />
                      )}
                    </div>
                  </div>
                </motion.button>
              ))}
            </AnimatePresence>
          )}
        </div>
      </div>

      {/* Right panel — thread */}
      <div className="flex-1 flex flex-col bg-[#0F0F1A]">
        {!selectedId ? (
          <div className="flex flex-col items-center justify-center h-full gap-3">
            <div className="w-12 h-12 rounded-xl bg-[#1E1E35] flex items-center justify-center">
              <MessageSquare size={22} className="text-[#2A2A45]" />
            </div>
            <p className="text-sm text-[#4A4A6A]">Select a conversation</p>
          </div>
        ) : (
          <>
            {/* Thread header */}
            <div className="flex items-center gap-3 px-5 py-3 border-b border-[#1E1E35] bg-[#16162A]">
              <div className="w-8 h-8 rounded-full bg-[#1E1E35] flex items-center justify-center">
                {selected && channelIcon[selected.channel]}
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-[#F1F1F5]">{selected?.from_contact}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  {selected && <ChannelBadge channel={selected.channel} />}
                  {selected && <StatusBadge status={selected.escalated ? 'escalated' : selected.status} />}
                </div>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {msgsLoading ? (
                [...Array(4)].map((_, i) => (
                  <div key={i} className={`flex ${i % 2 === 0 ? 'justify-start' : 'justify-end'}`}>
                    <div className="skeleton h-12 w-48 rounded-xl" />
                  </div>
                ))
              ) : !messages || messages.length === 0 ? (
                <div className="flex items-center justify-center h-full">
                  <p className="text-xs text-[#4A4A6A]">No messages in this conversation</p>
                </div>
              ) : (
                <AnimatePresence>
                  {messages.map((msg, i) => {
                    const isOutbound = msg.direction === 'outbound'
                    return (
                      <motion.div
                        key={msg.id}
                        initial={{ opacity: 0, y: 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.03, duration: 0.15 }}
                        className={`flex ${isOutbound ? 'justify-end' : 'justify-start'}`}
                      >
                        <div className={`max-w-xs lg:max-w-md xl:max-w-lg ${isOutbound ? 'items-end' : 'items-start'} flex flex-col gap-1`}>
                          {/* Sender label */}
                          <div className={`flex items-center gap-1 ${isOutbound ? 'flex-row-reverse' : ''}`}>
                            {isOutbound
                              ? <Bot size={10} className="text-indigo-400" />
                              : <User size={10} className="text-[#64748B]" />
                            }
                            <span className="text-[10px] text-[#4A4A6A]">
                              {msg.sent_by === 'ai' ? 'AI' : msg.sent_by === 'human' ? 'Agent' : 'Customer'}
                            </span>
                          </div>

                          {/* Bubble */}
                          <div className={`px-4 py-2.5 rounded-2xl text-sm leading-relaxed ${
                            isOutbound
                              ? 'bg-indigo-500 text-white rounded-br-sm'
                              : 'bg-[#1E1E35] text-[#F1F1F5] rounded-bl-sm'
                          }`}>
                            {msg.content}
                          </div>

                          <span className="text-[10px] text-[#4A4A6A]">
                            {msg.created_at ? formatRelativeTime(msg.created_at) : ''}
                          </span>
                        </div>
                      </motion.div>
                    )
                  })}
                </AnimatePresence>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}