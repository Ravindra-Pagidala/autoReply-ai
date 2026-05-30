'use client'

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Bot, Send, Sparkles, Users, ChevronDown, ChevronUp } from 'lucide-react'
import { get, post } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Skeleton } from '@/components/ui/Skeleton'
import { useToast } from '@/components/ui/Toast'
import { ChannelBadge } from '@/components/ui/Badge'
import type {
  Lead,
  PaginatedResponse,
  SalesAgentPreview,
  SalesAgentSendResponse,
} from '@/types'

type Step = 'configure' | 'preview'

const STATUS_COLORS: Record<string, string> = {
  new: 'bg-indigo-500/10 text-indigo-400',
  follow_up: 'bg-amber-500/10 text-amber-400',
  resolved: 'bg-green-500/10 text-green-400',
  lost: 'bg-[#1E1E35] text-[#64748B]',
}

export default function SalesAgentPage() {
  const toast = useToast()
  const [step, setStep] = useState<Step>('configure')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [goal, setGoal] = useState('')
  const [previews, setPreviews] = useState<SalesAgentPreview[]>([])
  const [messages, setMessages] = useState<Record<string, string>>({})
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  const [results, setResults] = useState<SalesAgentSendResponse | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['sales-agent-leads'],
    queryFn: () =>
      get<PaginatedResponse<Lead>>('/dashboard/leads?page=1&page_size=100'),
  })

  const leads = data?.data ?? []
  const allSelected = leads.length > 0 && selected.size === leads.length

  const toggleAll = () =>
    setSelected(allSelected ? new Set() : new Set(leads.map((l) => l.id)))

  const toggle = (id: string) => {
    const next = new Set(selected)
    next.has(id) ? next.delete(id) : next.add(id)
    setSelected(next)
  }

  const toggleExpand = (id: string) => {
    const next = new Set(expanded)
    next.has(id) ? next.delete(id) : next.add(id)
    setExpanded(next)
  }

  const generateMutation = useMutation({
    mutationFn: () =>
      post<SalesAgentPreview[]>('/dashboard/sales-agent/generate', {
        lead_ids: [...selected],
        goal,
      }),
    onSuccess: (data) => {
      setPreviews(data)
      const init: Record<string, string> = {}
      data.forEach((p) => { init[p.lead_id] = p.message })
      setMessages(init)
      setExpanded(new Set(data.map((p) => p.lead_id)))
      setStep('preview')
    },
    onError: (e) => toast.error('Generation failed', (e as Error).message),
  })

  const sendMutation = useMutation({
    mutationFn: () =>
      post<SalesAgentSendResponse>('/dashboard/sales-agent/send', {
        items: previews
          .filter((p) => p.can_send)
          .map((p) => ({
            lead_id: p.lead_id,
            to: p.to!,
            channel: p.channel,
            message: messages[p.lead_id] ?? p.message,
          })),
      }),
    onSuccess: (data) => {
      setResults(data)
      toast.success(`Campaign sent! ${data.sent} delivered, ${data.failed} failed.`)
    },
    onError: (e) => toast.error('Send failed', (e as Error).message),
  })

  const resultMap = new Map(results?.results.map((r) => [r.lead_id, r]))
  const sendableCount = previews.filter((p) => p.can_send).length

  return (
    <div className="p-6 max-w-5xl mx-auto">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6">
        <div className="w-9 h-9 rounded-lg bg-indigo-500/10 flex items-center justify-center">
          <Bot size={18} className="text-indigo-400" />
        </div>
        <div>
          <h2 className="text-lg font-semibold text-[#F1F1F5]">AI Sales Agent</h2>
          <p className="text-xs text-[#64748B] mt-0.5">
            Generate personalised outreach messages for your leads, review, then send
          </p>
        </div>
      </div>

      {/* Step indicator */}
      <div className="flex items-center gap-2 mb-6">
        {(['configure', 'preview'] as Step[]).map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <button
              onClick={() => step === 'preview' && s === 'configure' && setStep('configure')}
              className={`flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full transition-colors ${
                step === s
                  ? 'bg-indigo-500 text-white'
                  : s === 'configure' && step === 'preview'
                  ? 'bg-[#1E1E35] text-[#94A3B8] cursor-pointer hover:text-[#F1F1F5]'
                  : 'bg-[#1E1E35] text-[#4A4A6A] cursor-default'
              }`}
            >
              <span className="w-4 h-4 rounded-full border border-current flex items-center justify-center text-[10px]">
                {i + 1}
              </span>
              {s === 'configure' ? 'Select & Configure' : 'Preview & Send'}
            </button>
            {i < 1 && <div className="w-6 h-px bg-[#1E1E35]" />}
          </div>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {step === 'configure' ? (
          <motion.div
            key="configure"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.15 }}
            className="grid grid-cols-1 lg:grid-cols-2 gap-6"
          >
            {/* Lead selector */}
            <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-[#1E1E35]">
                <div className="flex items-center gap-2">
                  <Users size={14} className="text-[#64748B]" />
                  <span className="text-xs font-medium text-[#F1F1F5]">
                    Leads ({leads.length})
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
                        <Skeleton className="h-3 w-32" />
                        <Skeleton className="h-2.5 w-48" />
                      </div>
                    </div>
                  ))
                ) : leads.length === 0 ? (
                  <div className="px-4 py-12 text-center">
                    <p className="text-sm text-[#4A4A6A]">No leads yet</p>
                  </div>
                ) : (
                  leads.map((lead) => {
                    const isSelected = selected.has(lead.id)
                    return (
                      <div
                        key={lead.id}
                        onClick={() => toggle(lead.id)}
                        className={`flex items-start gap-3 px-4 py-3 cursor-pointer transition-colors duration-100 ${
                          isSelected
                            ? 'bg-indigo-500/5 hover:bg-indigo-500/10'
                            : 'hover:bg-[#1E1E35]/30'
                        }`}
                      >
                        <div
                          className={`mt-0.5 w-4 h-4 rounded border flex items-center justify-center flex-shrink-0 transition-colors ${
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
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="text-xs font-medium text-[#F1F1F5]">
                              {lead.name ?? 'Unknown'}
                            </p>
                            <ChannelBadge channel={lead.channel} />
                            <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full capitalize ${STATUS_COLORS[lead.status] ?? ''}`}>
                              {lead.status}
                            </span>
                          </div>
                          {lead.query && (
                            <p className="text-[10px] text-[#64748B] mt-0.5 line-clamp-1">
                              {lead.query}
                            </p>
                          )}
                          <p className="text-[10px] text-[#4A4A6A] mt-0.5">
                            {lead.phone ?? lead.email ?? 'No contact'}
                          </p>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
              {selected.size > 0 && (
                <div className="px-4 py-2.5 border-t border-[#1E1E35] bg-[#111120]">
                  <p className="text-xs text-indigo-400">
                    {selected.size} lead{selected.size !== 1 ? 's' : ''} selected
                  </p>
                </div>
              )}
            </div>

            {/* Campaign goal */}
            <div className="flex flex-col gap-4">
              <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl overflow-hidden">
                <div className="px-4 py-3 border-b border-[#1E1E35]">
                  <p className="text-xs font-medium text-[#F1F1F5]">Campaign Goal</p>
                  <p className="text-[10px] text-[#64748B] mt-0.5">
                    Describe what you want the AI to promote or achieve
                  </p>
                </div>
                <div className="p-4">
                  <textarea
                    value={goal}
                    onChange={(e) => setGoal(e.target.value)}
                    rows={5}
                    placeholder="e.g. Offer 20% Diwali discount on all haircut services and encourage booking this week"
                    className="w-full bg-[#111120] border border-[#1E1E35] rounded-lg px-3 py-2.5 text-xs text-[#F1F1F5] placeholder:text-[#4A4A6A] focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition-all resize-none leading-relaxed"
                  />
                </div>
              </div>

              <div className="bg-indigo-500/5 border border-indigo-500/20 rounded-xl p-4 space-y-1.5">
                <p className="text-xs font-medium text-indigo-400">How it works</p>
                <p className="text-[10px] text-[#64748B] leading-relaxed">
                  The AI reads each lead's name and previous query, then writes a personalised
                  message aligned with your goal. You can edit every message before sending.
                </p>
              </div>

              <Button
                variant="primary"
                size="md"
                icon={<Sparkles size={14} />}
                onClick={() => generateMutation.mutate()}
                disabled={selected.size === 0 || !goal.trim() || generateMutation.isPending}
                loading={generateMutation.isPending}
                className="w-full justify-center"
              >
                {generateMutation.isPending
                  ? `Generating messages…`
                  : `Generate for ${selected.size} lead${selected.size !== 1 ? 's' : ''}`}
              </Button>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="preview"
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
            transition={{ duration: 0.15 }}
            className="space-y-4"
          >
            {/* Preview list */}
            <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-[#1E1E35]">
                <p className="text-xs font-medium text-[#F1F1F5]">
                  Generated Messages ({previews.length})
                </p>
                <p className="text-[10px] text-[#64748B]">
                  {sendableCount} can be sent · click a row to edit
                </p>
              </div>
              <div className="divide-y divide-[#1E1E35]/50">
                {previews.map((preview) => {
                  const res = resultMap.get(preview.lead_id)
                  const isOpen = expanded.has(preview.lead_id)
                  return (
                    <div key={preview.lead_id}>
                      <div
                        className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[#1E1E35]/30 transition-colors"
                        onClick={() => toggleExpand(preview.lead_id)}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <p className="text-xs font-medium text-[#F1F1F5]">
                              {preview.name ?? 'Unknown'}
                            </p>
                            <ChannelBadge channel={preview.channel} />
                            {!preview.can_send && (
                              <span className="text-[10px] bg-amber-500/10 text-amber-400 px-1.5 py-0.5 rounded-full">
                                No contact
                              </span>
                            )}
                            {res && (
                              <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
                                res.success
                                  ? 'bg-green-500/10 text-green-400'
                                  : 'bg-red-500/10 text-red-400'
                              }`}>
                                {res.success ? 'Sent' : 'Failed'}
                              </span>
                            )}
                          </div>
                          <p className="text-[10px] text-[#64748B] mt-0.5 truncate">
                            {preview.to ?? '—'} · {(messages[preview.lead_id] ?? preview.message).slice(0, 60)}…
                          </p>
                        </div>
                        {isOpen
                          ? <ChevronUp size={14} className="text-[#4A4A6A] flex-shrink-0" />
                          : <ChevronDown size={14} className="text-[#4A4A6A] flex-shrink-0" />
                        }
                      </div>
                      <AnimatePresence>
                        {isOpen && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            transition={{ duration: 0.15 }}
                            className="overflow-hidden"
                          >
                            <div className="px-4 pb-3">
                              <textarea
                                value={messages[preview.lead_id] ?? preview.message}
                                onChange={(e) =>
                                  setMessages((prev) => ({
                                    ...prev,
                                    [preview.lead_id]: e.target.value,
                                  }))
                                }
                                rows={4}
                                className="w-full bg-[#111120] border border-[#1E1E35] rounded-lg px-3 py-2.5 text-xs text-[#F1F1F5] focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition-all resize-none leading-relaxed"
                              />
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </div>
                  )
                })}
              </div>
            </div>

            {/* Actions */}
            <div className="flex items-center gap-3">
              <Button
                variant="secondary"
                size="md"
                onClick={() => { setStep('configure'); setResults(null) }}
                className="flex-shrink-0"
              >
                Back
              </Button>
              <Button
                variant="primary"
                size="md"
                icon={<Send size={14} />}
                onClick={() => sendMutation.mutate()}
                disabled={sendableCount === 0 || sendMutation.isPending}
                loading={sendMutation.isPending}
                className="flex-1 justify-center"
              >
                {sendMutation.isPending
                  ? 'Sending campaign…'
                  : `Send to ${sendableCount} lead${sendableCount !== 1 ? 's' : ''}`}
              </Button>
            </div>

            {/* Results summary */}
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
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
