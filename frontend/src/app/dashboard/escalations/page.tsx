'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { AlertTriangle, CheckCircle, MessageSquare } from 'lucide-react'
import { get, patch } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import { ChannelBadge, StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { Textarea } from '@/components/ui/Input'
import { useToast } from '@/components/ui/Toast'
import type { PaginatedResponse, Escalation } from '@/types'

export default function EscalationsPage() {
  const toast = useToast()
  const qc = useQueryClient()
  const [selected, setSelected] = useState<Escalation | null>(null)
  const [reply, setReply] = useState('')
  const [statusFilter, setStatusFilter] = useState('open')

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['escalations', statusFilter],
    queryFn: () =>
      get<PaginatedResponse<Escalation>>(
        `/dashboard/escalations?page_size=30${statusFilter !== 'all' ? `&status=${statusFilter}` : ''}`
      ),
    refetchInterval: 15000,
  })

  const resolveMutation = useMutation({
    mutationFn: (id: string) =>
      patch(`/dashboard/escalations/${id}/resolve`, { human_reply: reply }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['escalations'] })
      qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
      toast.success('Escalation resolved', 'Reply sent to customer')
      setSelected(null)
      setReply('')
    },
    onError: (e) => toast.error('Failed to resolve', (e as Error).message),
  })

  const escalations = data?.data ?? []

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-[#F1F1F5]">Escalations</h2>
          <p className="text-xs text-[#64748B] mt-0.5">
            Conversations that need human attention
          </p>
        </div>
        <div className="flex gap-1.5">
          {['open', 'assigned', 'resolved', 'all'].map((s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-3 h-8 rounded-lg text-xs font-medium capitalize transition-all duration-150 ${
                statusFilter === s
                  ? 'bg-indigo-500 text-white'
                  : 'bg-[#1E1E35] text-[#64748B] hover:text-[#F1F1F5]'
              }`}
            >
              {s}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className="space-y-3">
        {isLoading ? (
          [...Array(4)].map((_, i) => (
            <div key={i} className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5">
              <div className="skeleton h-4 w-48 mb-3 rounded" />
              <div className="skeleton h-3 w-64 rounded" />
            </div>
          ))
        ) : isError ? (
          <div className="flex flex-col items-center gap-3 py-16">
            <p className="text-sm text-[#4A4A6A]">Failed to load escalations</p>
            <Button variant="ghost" size="sm" onClick={() => refetch()}>Retry</Button>
          </div>
        ) : escalations.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-16">
            <div className="w-12 h-12 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
              <CheckCircle size={22} className="text-emerald-400" />
            </div>
            <p className="text-sm text-[#F1F1F5] font-medium">All clear!</p>
            <p className="text-xs text-[#4A4A6A]">No {statusFilter !== 'all' ? statusFilter : ''} escalations</p>
          </div>
        ) : (
          <AnimatePresence>
            {escalations.map((esc, i) => (
              <motion.div
                key={esc.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04, duration: 0.2 }}
                className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5 hover:border-[#2A2A45] transition-colors duration-150"
              >
                <div className="flex items-start justify-between gap-4">
                  <div className="flex items-start gap-3 flex-1 min-w-0">
                    <div className="w-9 h-9 rounded-lg bg-red-500/10 border border-red-500/20 flex items-center justify-center flex-shrink-0 mt-0.5">
                      <AlertTriangle size={16} className="text-red-400" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-semibold text-[#F1F1F5]">{esc.from_contact}</p>
                        <ChannelBadge channel={esc.channel} />
                        <StatusBadge status={esc.status} />
                      </div>
                      <p className="text-xs text-[#64748B] mt-1">
                        Reason: <span className="text-[#94A3B8]">{esc.reason.replace(/_/g, ' ')}</span>
                      </p>
                      {esc.human_reply && (
                        <div className="mt-2 p-3 rounded-lg bg-emerald-500/5 border border-emerald-500/10">
                          <p className="text-xs text-emerald-400 font-medium mb-1">Your reply:</p>
                          <p className="text-xs text-[#94A3B8]">{esc.human_reply}</p>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-3 flex-shrink-0">
                    <span className="text-xs text-[#4A4A6A]">
                      {esc.created_at ? formatRelativeTime(esc.created_at) : ''}
                    </span>
                    {esc.status !== 'resolved' && (
                      <Button
                        size="sm"
                        icon={<MessageSquare size={12} />}
                        onClick={() => { setSelected(esc); setReply('') }}
                      >
                        Resolve
                      </Button>
                    )}
                  </div>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>

      {/* Resolve modal */}
      <Modal
        open={!!selected}
        onClose={() => setSelected(null)}
        title="Resolve Escalation"
        description={`Reply to ${selected?.from_contact} via ${selected?.channel}`}
        size="md"
      >
        <div className="space-y-4">
          <div className="p-3 rounded-lg bg-[#111120] border border-[#1E1E35]">
            <p className="text-xs text-[#64748B] mb-1">Escalation reason</p>
            <p className="text-sm text-[#94A3B8]">
              {selected?.reason.replace(/_/g, ' ')}
            </p>
          </div>
          <Textarea
            label="Your Reply"
            placeholder="Type your reply to the customer..."
            value={reply}
            onChange={(e) => setReply(e.target.value)}
            rows={4}
            required
          />
          <div className="flex gap-3 justify-end">
            <Button variant="secondary" onClick={() => setSelected(null)}>
              Cancel
            </Button>
            <Button
              onClick={() => selected && resolveMutation.mutate(selected.id)}
              loading={resolveMutation.isPending}
              disabled={!reply.trim()}
            >
              Send & Resolve
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}