'use client'

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Megaphone, Send, Users } from 'lucide-react'
import { get, post } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { useToast } from '@/components/ui/Toast'
import type { BroadcastContact, BroadcastSendResponse } from '@/types'

const DEFAULT_MESSAGE = `🎉 Happy Diwali from our team! 🪔

This festive season, we have exclusive offers just for you:
✨ 20% off on all services this week
🎁 Special Diwali packages available
💫 Book today and get a free consultation!

Reply to this message to claim your offer or book an appointment.

Wishing you and your family a very Happy Diwali! 🎆`

export default function BroadcastPage() {
  const toast = useToast()
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [message, setMessage] = useState(DEFAULT_MESSAGE)
  const [results, setResults] = useState<BroadcastSendResponse | null>(null)

  const { data: contacts = [], isLoading } = useQuery({
    queryKey: ['broadcast-contacts'],
    queryFn: () => get<BroadcastContact[]>('/dashboard/broadcast/contacts'),
  })

  const allSelected = contacts.length > 0 && selected.size === contacts.length

  const toggleAll = () => {
    setSelected(allSelected ? new Set() : new Set(contacts.map((c) => c.phone)))
  }

  const toggle = (phone: string) => {
    const next = new Set(selected)
    next.has(phone) ? next.delete(phone) : next.add(phone)
    setSelected(next)
  }

  const sendMutation = useMutation({
    mutationFn: () =>
      post<BroadcastSendResponse>('/dashboard/broadcast/send', {
        contacts: [...selected],
        message,
      }),
    onSuccess: (data) => {
      setResults(data)
      toast.success(`Campaign sent! ${data.sent} delivered, ${data.failed} failed.`)
    },
    onError: (e) => toast.error('Campaign failed', (e as Error).message),
  })

  const resultMap = new Map(results?.results.map((r) => [r.phone, r]))

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-9 h-9 rounded-lg bg-indigo-500/10 flex items-center justify-center">
          <Megaphone size={18} className="text-indigo-400" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-[#F1F1F5]">WhatsApp Broadcast</h2>
          <p className="text-xs text-[#64748B] mt-0.5">
            Send a message to all or selected WhatsApp contacts
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Contacts panel */}
        <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-[#1E1E35]">
            <div className="flex items-center gap-2">
              <Users size={14} className="text-[#64748B]" />
              <span className="text-xs font-medium text-[#F1F1F5]">
                Contacts ({contacts.length})
              </span>
            </div>
            <button
              onClick={toggleAll}
              className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors"
            >
              {allSelected ? 'Deselect All' : 'Select All'}
            </button>
          </div>

          <div className="max-h-[420px] overflow-y-auto divide-y divide-[#1E1E35]/50">
            {isLoading ? (
              [...Array(5)].map((_, i) => (
                <div key={i} className="flex items-center gap-3 px-4 py-3">
                  <Skeleton className="w-4 h-4 rounded flex-shrink-0" />
                  <div className="flex-1 space-y-1.5">
                    <Skeleton className="h-3 w-40" />
                    <Skeleton className="h-2.5 w-24" />
                  </div>
                </div>
              ))
            ) : contacts.length === 0 ? (
              <div className="px-4 py-12 text-center">
                <Megaphone size={24} className="text-[#2A2A45] mx-auto mb-2" />
                <p className="text-sm text-[#4A4A6A]">No WhatsApp contacts yet</p>
                <p className="text-xs text-[#4A4A6A] mt-1">
                  Contacts appear after customers message you on WhatsApp
                </p>
              </div>
            ) : (
              contacts.map((contact) => {
                const res = resultMap.get(contact.phone)
                const isSelected = selected.has(contact.phone)
                return (
                  <motion.div
                    key={contact.phone}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    onClick={() => toggle(contact.phone)}
                    className={`flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors duration-100 ${
                      isSelected
                        ? 'bg-indigo-500/5 hover:bg-indigo-500/10'
                        : 'hover:bg-[#1E1E35]/30'
                    }`}
                  >
                    {/* Checkbox */}
                    <div
                      className={`w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${
                        isSelected ? 'bg-indigo-500 border-indigo-500' : 'border-[#2A2A45]'
                      }`}
                    >
                      {isSelected && (
                        <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 10 8">
                          <path
                            d="M1 4l3 3 5-6"
                            stroke="currentColor"
                            strokeWidth="1.5"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-[#F1F1F5]">{contact.phone}</p>
                      {contact.last_seen && (
                        <p className="text-[10px] text-[#64748B] mt-0.5">
                          Last seen {formatRelativeTime(contact.last_seen)}
                        </p>
                      )}
                    </div>

                    {res && (
                      <span
                        className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                          res.success
                            ? 'bg-green-500/10 text-green-400'
                            : 'bg-red-500/10 text-red-400'
                        }`}
                      >
                        {res.success ? 'Sent' : 'Failed'}
                      </span>
                    )}
                  </motion.div>
                )
              })
            )}
          </div>

          {selected.size > 0 && (
            <div className="px-4 py-2.5 border-t border-[#1E1E35] bg-[#111120]">
              <p className="text-xs text-indigo-400">
                {selected.size} contact{selected.size !== 1 ? 's' : ''} selected
              </p>
            </div>
          )}
        </div>

        {/* Message + send panel */}
        <div className="flex flex-col gap-4">
          <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-[#1E1E35]">
              <p className="text-xs font-medium text-[#F1F1F5]">Campaign Message</p>
              <p className="text-[10px] text-[#64748B] mt-0.5">
                Customise before sending
              </p>
            </div>
            <div className="p-4">
              <textarea
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                rows={12}
                className="w-full bg-[#111120] border border-[#1E1E35] rounded-lg px-3 py-2.5 text-xs text-[#F1F1F5] placeholder:text-[#4A4A6A] focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition-all resize-none leading-relaxed"
                placeholder="Type your broadcast message..."
              />
              <p className="text-[10px] text-[#64748B] mt-1.5 text-right">
                {message.length} chars
              </p>
            </div>
          </div>

          <Button
            variant="primary"
            size="md"
            icon={<Send size={14} />}
            onClick={() => sendMutation.mutate()}
            disabled={selected.size === 0 || !message.trim() || sendMutation.isPending}
            loading={sendMutation.isPending}
            className="w-full justify-center"
          >
            {sendMutation.isPending
              ? `Sending to ${selected.size} contacts…`
              : `Send to ${selected.size} contact${selected.size !== 1 ? 's' : ''}`}
          </Button>

          {results && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-4"
            >
              <p className="text-xs font-medium text-[#F1F1F5] mb-3">Campaign Results</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-green-400">{results.sent}</p>
                  <p className="text-[10px] text-[#64748B] mt-0.5">Delivered</p>
                </div>
                <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-red-400">{results.failed}</p>
                  <p className="text-[10px] text-[#64748B] mt-0.5">Failed</p>
                </div>
              </div>
            </motion.div>
          )}
        </div>
      </div>
    </div>
  )
}
