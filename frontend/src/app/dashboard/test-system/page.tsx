'use client'

import { useState, useRef, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, CheckCircle, XCircle, MessageSquare, Phone, Mail, Trophy } from 'lucide-react'
import { post, get } from '@/lib/api'
import { formatMs } from '@/lib/utils'
import { Button } from '@/components/ui/Button'
import { useToast } from '@/components/ui/Toast'
import type { TestRun, TestResult } from '@/types'

const channelIcon: Record<string, React.ReactNode> = {
  whatsapp: <MessageSquare size={12} className="text-[#25D366]" />,
  voice:    <Phone size={12} className="text-blue-400" />,
  email:    <Mail size={12} className="text-violet-400" />,
}

export default function TestSystemPage() {
  const toast = useToast()
  const qc = useQueryClient()
  const resultsRef = useRef<HTMLDivElement>(null)
  const [activeRunId, setActiveRunId] = useState<string | null>(null)
  const [testType, setTestType] = useState<'all' | 'whatsapp' | 'voice' | 'email'>('all')
  const [counts, setCounts] = useState({ whatsapp: 10, voice: 5, email: 10 })

  const { data: runs } = useQuery({
    queryKey: ['test-runs'],
    queryFn: () => get<TestRun[]>('/test/runs'),
  })

  const { data: results } = useQuery({
    queryKey: ['test-results', activeRunId],
    queryFn: () => get<TestResult[]>(`/test/runs/${activeRunId}/results`),
    enabled: !!activeRunId,
    refetchInterval: activeRunId ? 2000 : false,
  })

  const runMutation = useMutation({
    mutationFn: () =>
      post<TestRun>('/test/run', {
        test_type: testType,
        whatsapp_count: counts.whatsapp,
        voice_count: counts.voice,
        email_count: counts.email,
      }),
    onSuccess: (run) => {
      setActiveRunId(run.id)
      qc.invalidateQueries({ queryKey: ['test-runs'] })
      toast.info('Test started', `Firing ${testType === 'all' ? 'all channels' : testType}...`)
    },
    onError: (e) => toast.error('Test failed to start', (e as Error).message),
  })

  useEffect(() => {
    if (results?.length && resultsRef.current) {
      resultsRef.current.scrollTop = resultsRef.current.scrollHeight
    }
  }, [results?.length])

  const activeRun = runs?.find((r) => r.id === activeRunId)
  const isRunning = activeRun?.status === 'running' || runMutation.isPending
  const successRate = activeRun
    ? Math.round((activeRun.total_success / Math.max(activeRun.total_sent, 1)) * 100)
    : 0

  const getReplyPreview = (reply: string | null): string => {
    if (!reply) return ''
    return reply.length > 40 ? reply.slice(0, 40) + '...' : reply
  }

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-[#F1F1F5]">Test System</h2>
        <p className="text-xs text-[#64748B] mt-0.5">
          Fire automated tests across all channels simultaneously
        </p>
      </div>

      {/* Control panel */}
      <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5">
        <h3 className="text-sm font-semibold text-[#F1F1F5] mb-4">Configure Test</h3>

        <div className="flex gap-2 mb-5 flex-wrap">
          {(['all', 'whatsapp', 'voice', 'email'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTestType(t)}
              className={`flex items-center gap-1.5 px-3 h-9 rounded-lg text-xs font-medium capitalize transition-all duration-150 ${
                testType === t
                  ? 'bg-indigo-500 text-white'
                  : 'bg-[#111120] text-[#64748B] border border-[#1E1E35] hover:border-indigo-500/50'
              }`}
            >
              {t !== 'all' && channelIcon[t]}
              {t === 'all' ? 'All Channels' : t}
            </button>
          ))}
        </div>

        {(testType === 'all' || testType === 'whatsapp') && (
          <div className="flex items-center gap-4 mb-3">
            <label className="text-xs text-[#64748B] w-32 flex items-center gap-1.5">
              {channelIcon.whatsapp} WhatsApp
            </label>
            <input type="range" min="1" max="20" step="1"
              value={counts.whatsapp}
              onChange={(e) => setCounts((c) => ({ ...c, whatsapp: Number(e.target.value) }))}
              className="flex-1 accent-indigo-500"
              aria-label="WhatsApp count" />
            <span className="text-xs font-mono text-indigo-400 w-6 text-right">{counts.whatsapp}</span>
          </div>
        )}
        {(testType === 'all' || testType === 'voice') && (
          <div className="flex items-center gap-4 mb-3">
            <label className="text-xs text-[#64748B] w-32 flex items-center gap-1.5">
              {channelIcon.voice} Voice
            </label>
            <input type="range" min="1" max="10" step="1"
              value={counts.voice}
              onChange={(e) => setCounts((c) => ({ ...c, voice: Number(e.target.value) }))}
              className="flex-1 accent-indigo-500"
              aria-label="Voice count" />
            <span className="text-xs font-mono text-indigo-400 w-6 text-right">{counts.voice}</span>
          </div>
        )}
        {(testType === 'all' || testType === 'email') && (
          <div className="flex items-center gap-4 mb-5">
            <label className="text-xs text-[#64748B] w-32 flex items-center gap-1.5">
              {channelIcon.email} Email
            </label>
            <input type="range" min="1" max="20" step="1"
              value={counts.email}
              onChange={(e) => setCounts((c) => ({ ...c, email: Number(e.target.value) }))}
              className="flex-1 accent-indigo-500"
              aria-label="Email count" />
            <span className="text-xs font-mono text-indigo-400 w-6 text-right">{counts.email}</span>
          </div>
        )}

        <motion.div whileTap={{ scale: 0.98 }}>
          <Button
            className="w-full h-12 text-base font-semibold"
            onClick={() => runMutation.mutate()}
            loading={isRunning}
            disabled={isRunning}
            icon={<Zap size={18} />}
          >
            {isRunning ? 'Running Tests...' : 'Fire Test'}
          </Button>
        </motion.div>
      </div>

      {/* Results panel */}
      {activeRunId && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-[#16162A] border border-[#1E1E35] rounded-xl overflow-hidden"
        >
          <div className="flex items-center justify-between px-5 py-4 border-b border-[#1E1E35]">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold text-[#F1F1F5]">Live Results</h3>
              {isRunning && (
                <span className="flex items-center gap-1.5 text-xs text-amber-400">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                  Running
                </span>
              )}
              {activeRun?.status === 'completed' && (
                <span className="flex items-center gap-1.5 text-xs text-emerald-400">
                  <CheckCircle size={12} /> Complete
                </span>
              )}
            </div>
            {activeRun && (
              <div className="flex items-center gap-4 text-xs text-[#64748B]">
                <span>{activeRun.total_success}/{activeRun.total_sent} handled</span>
                {activeRun.avg_response_ms > 0 && (
                  <span>Avg {formatMs(activeRun.avg_response_ms)}</span>
                )}
              </div>
            )}
          </div>

          {activeRun && activeRun.total_sent > 0 && (
            <div className="px-5 py-2 border-b border-[#1E1E35]">
              <div className="flex justify-between text-[10px] text-[#4A4A6A] mb-1">
                <span>{successRate}% success rate</span>
                <span>{activeRun.total_failed} failed</span>
              </div>
              <div className="h-1.5 bg-[#1E1E35] rounded-full overflow-hidden">
                <motion.div
                  className="h-full bg-indigo-500 rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${successRate}%` }}
                  transition={{ duration: 0.5 }}
                />
              </div>
            </div>
          )}

          <div
            ref={resultsRef}
            className="max-h-72 overflow-y-auto font-mono text-xs divide-y divide-[#1E1E35]/50"
          >
            {!results || results.length === 0 ? (
              <div className="p-5 text-center text-[#4A4A6A]">
                {isRunning ? 'Waiting for results...' : 'No results yet'}
              </div>
            ) : (
              <AnimatePresence>
                {results.map((r, i) => {
                  const preview = getReplyPreview(r.reply_received)
                  return (
                    <motion.div
                      key={r.id}
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: Math.min(i * 0.03, 0.3) }}
                      className={`flex items-center gap-3 px-5 py-2.5 ${
                        r.success ? 'bg-emerald-500/[0.03]' : 'bg-red-500/[0.03]'
                      }`}
                    >
                      {r.success
                        ? <CheckCircle size={12} className="text-emerald-400 flex-shrink-0" />
                        : <XCircle size={12} className="text-red-400 flex-shrink-0" />
                      }
                      <span className="flex-shrink-0">
                        {channelIcon[r.channel] ?? null}
                      </span>
                      <span className={r.success ? 'text-emerald-300' : 'text-red-300'}>
                        {r.success
                          ? `${r.channel} replied in ${formatMs(r.response_time_ms ?? 0)}`
                          : `${r.channel} failed: ${r.error_reason ?? 'unknown'}`
                        }
                      </span>
                      {preview && (
                        <span className="text-[#4A4A6A] truncate flex-1">
                          &ldquo;{preview}&rdquo;
                        </span>
                      )}
                    </motion.div>
                  )
                })}
              </AnimatePresence>
            )}
          </div>

          {activeRun?.status === 'completed' && (
            <motion.div
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.3 }}
              className="m-4 p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/20"
            >
              <div className="flex items-center gap-2 mb-3">
                <Trophy size={16} className="text-indigo-400" />
                <span className="text-sm font-semibold text-indigo-400">Test Complete!</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'Handled', value: `${activeRun.total_success}/${activeRun.total_sent}` },
                  { label: 'Success rate', value: `${successRate}%` },
                  { label: 'Avg response', value: formatMs(activeRun.avg_response_ms) },
                  { label: 'Leads captured', value: String(activeRun.leads_captured) },
                ].map(({ label, value }) => (
                  <div key={label} className="text-center">
                    <p className="text-lg font-bold text-[#F1F1F5]">{value}</p>
                    <p className="text-[10px] text-[#64748B]">{label}</p>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </motion.div>
      )}

      {/* Past runs */}
      {runs && runs.length > 0 && (
        <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-[#1E1E35]">
            <h3 className="text-sm font-semibold text-[#F1F1F5]">Past Runs</h3>
          </div>
          <div className="divide-y divide-[#1E1E35]/50">
            {runs.slice(0, 5).map((run) => (
              <button
                key={run.id}
                onClick={() => setActiveRunId(run.id)}
                className={`w-full flex items-center gap-4 px-5 py-3 text-left hover:bg-[#1E1E35]/50 transition-colors ${
                  activeRunId === run.id ? 'bg-indigo-500/5' : ''
                }`}
              >
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${
                  run.status === 'completed' ? 'bg-emerald-400' : 'bg-amber-400 animate-pulse'
                }`} />
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium text-[#F1F1F5] capitalize">{run.test_type} test</p>
                  <p className="text-[10px] text-[#4A4A6A]">
                    {run.total_success}/{run.total_sent} handled · {formatMs(run.avg_response_ms)}
                  </p>
                </div>
                <span className="text-[10px] text-[#4A4A6A]">
                  {run.created_at ? new Date(run.created_at).toLocaleTimeString() : ''}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}