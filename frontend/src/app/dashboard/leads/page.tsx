'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import { Users, Download, Search } from 'lucide-react'
import { get, patch } from '@/lib/api'
import { formatRelativeTime, getChannelLabel } from '@/lib/utils'
import { ChannelBadge, StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { TableRowSkeleton } from '@/components/ui/Skeleton'
import { useToast } from '@/components/ui/Toast'
import type { PaginatedResponse, Lead } from '@/types'

const STATUS_OPTIONS = ['new', 'follow_up', 'resolved', 'lost'] as const
const CHANNEL_FILTERS = ['all', 'whatsapp', 'voice', 'email'] as const

export default function LeadsPage() {
  const toast = useToast()
  const qc = useQueryClient()
  const [channel, setChannel] = useState('all')
  const [status, setStatus] = useState('all')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['leads', channel, status, page],
    queryFn: () =>
      get<PaginatedResponse<Lead>>(
        `/dashboard/leads?page=${page}&page_size=20${channel !== 'all' ? `&channel=${channel}` : ''}${status !== 'all' ? `&status=${status}` : ''}`
      ),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      patch(`/dashboard/leads/${id}`, { status }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['leads'] })
      toast.success('Lead updated')
    },
    onError: (e) => toast.error('Failed to update lead', (e as Error).message),
  })

  const leads = data?.data ?? []
  const filtered = search
    ? leads.filter((l) =>
        [l.name, l.phone, l.email, l.query]
          .filter(Boolean)
          .some((v) => v!.toLowerCase().includes(search.toLowerCase()))
      )
    : leads

  const exportCSV = () => {
    if (!leads.length) return
    const headers = ['Name', 'Phone', 'Email', 'Channel', 'Query', 'Status', 'Created']
    const rows = leads.map((l) => [
      l.name ?? '', l.phone ?? '', l.email ?? '',
      l.channel, l.query ?? '', l.status,
      l.created_at ? new Date(l.created_at).toLocaleDateString() : '',
    ])
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'leads.csv'; a.click()
    URL.revokeObjectURL(url)
    toast.success('Leads exported')
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-[#F1F1F5]">Leads</h2>
          <p className="text-xs text-[#64748B] mt-0.5">
            {data?.total ?? 0} total leads captured
          </p>
        </div>
        <Button
          variant="secondary"
          size="sm"
          icon={<Download size={14} />}
          onClick={exportCSV}
        >
          Export CSV
        </Button>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3 mb-5">
        {/* Search */}
        <div className="relative flex-1 min-w-48 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#4A4A6A]" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search leads..."
            className="w-full h-9 pl-9 pr-3 rounded-lg bg-[#111120] border border-[#1E1E35] text-sm text-[#F1F1F5] placeholder:text-[#4A4A6A] focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 outline-none transition-all"
            aria-label="Search leads"
          />
        </div>

        {/* Channel filter */}
        <div className="flex gap-1.5">
          {CHANNEL_FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => { setChannel(f); setPage(1) }}
              className={`px-3 h-9 rounded-lg text-xs font-medium capitalize transition-all duration-150 ${
                channel === f
                  ? 'bg-indigo-500 text-white'
                  : 'bg-[#1E1E35] text-[#64748B] hover:text-[#F1F1F5]'
              }`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Status filter */}
        <select
          value={status}
          onChange={(e) => { setStatus(e.target.value); setPage(1) }}
          className="h-9 px-3 rounded-lg bg-[#111120] border border-[#1E1E35] text-xs text-[#94A3B8] outline-none focus:border-indigo-500 transition-all cursor-pointer"
          aria-label="Filter by status"
        >
          <option value="all">All Status</option>
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s} className="capitalize">{s.replace('_', ' ')}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" role="table" aria-label="Leads table">
            <thead>
              <tr className="border-b border-[#1E1E35]">
                {['Contact', 'Channel', 'Query', 'Status', 'Captured', 'Actions'].map((h) => (
                  <th
                    key={h}
                    scope="col"
                    className="px-4 py-3 text-left text-[10px] font-semibold text-[#4A4A6A] uppercase tracking-wider"
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#1E1E35]/50">
              {isLoading ? (
                [...Array(6)].map((_, i) => <TableRowSkeleton key={i} cols={6} />)
              ) : isError ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <p className="text-sm text-[#4A4A6A]">Failed to load leads</p>
                      <Button variant="ghost" size="sm" onClick={() => refetch()}>Retry</Button>
                    </div>
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <Users size={24} className="text-[#2A2A45]" />
                      <p className="text-sm text-[#4A4A6A]">No leads found</p>
                      <p className="text-xs text-[#4A4A6A]">Leads are captured automatically from conversations</p>
                    </div>
                  </td>
                </tr>
              ) : (
                filtered.map((lead, i) => (
                  <motion.tr
                    key={lead.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.02 }}
                    className="hover:bg-[#1E1E35]/30 transition-colors duration-100"
                  >
                    <td className="px-4 py-3">
                      <div>
                        <p className="text-xs font-medium text-[#F1F1F5]">
                          {lead.name ?? '—'}
                        </p>
                        <p className="text-[10px] text-[#64748B] mt-0.5">
                          {lead.phone ?? lead.email ?? '—'}
                        </p>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <ChannelBadge channel={lead.channel} />
                    </td>
                    <td className="px-4 py-3">
                      <p className="text-xs text-[#94A3B8] max-w-xs truncate">
                        {lead.query ?? '—'}
                      </p>
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={lead.status} />
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-xs text-[#64748B]">
                        {lead.created_at ? formatRelativeTime(lead.created_at) : '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <select
                        value={lead.status}
                        onChange={(e) =>
                          updateMutation.mutate({ id: lead.id, status: e.target.value })
                        }
                        className="h-7 px-2 rounded-lg bg-[#111120] border border-[#1E1E35] text-[10px] text-[#94A3B8] outline-none focus:border-indigo-500 cursor-pointer transition-all"
                        aria-label={`Update status for lead ${lead.name ?? lead.id}`}
                      >
                        {STATUS_OPTIONS.map((s) => (
                          <option key={s} value={s} className="capitalize">
                            {s.replace('_', ' ')}
                          </option>
                        ))}
                      </select>
                    </td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {data && data.total > 20 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-[#1E1E35]">
            <p className="text-xs text-[#64748B]">
              Showing {(page - 1) * 20 + 1}–{Math.min(page * 20, data.total)} of {data.total}
            </p>
            <div className="flex gap-2">
              <Button
                variant="secondary" size="sm"
                disabled={page === 1}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Button
                variant="secondary" size="sm"
                disabled={!data.has_more}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}