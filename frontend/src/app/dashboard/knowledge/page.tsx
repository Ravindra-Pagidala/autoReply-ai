'use client'

import { useState, useCallback } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { motion, AnimatePresence } from 'framer-motion'
import {
  BookOpen, Upload, Trash2, FileText,
  CheckCircle, AlertCircle, Clock,
  Sparkles, ThumbsUp, ThumbsDown, RefreshCw, Pencil,
} from 'lucide-react'
import { get, del, post, uploadFile } from '@/lib/api'
import { formatRelativeTime } from '@/lib/utils'
import { StatusBadge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { Modal } from '@/components/ui/Modal'
import { useToast } from '@/components/ui/Toast'
import type { KnowledgeBase } from '@/types'

// ── Types ──────────────────────────────────────────────────────────────────

interface FAQGap {
  question: string
  answer: string
  source_count: number
  approved?: boolean  // undefined = not reviewed, true = approved, false = rejected
}

// ── Status icon map ────────────────────────────────────────────────────────

const statusIcon: Record<string, React.ReactNode> = {
  trained:    <CheckCircle size={14} className="text-emerald-400" />,
  failed:     <AlertCircle size={14} className="text-red-400" />,
  processing: <Clock size={14} className="text-amber-400 animate-spin" />,
  pending:    <Clock size={14} className="text-[#64748B]" />,
}

// ── Component ──────────────────────────────────────────────────────────────

export default function KnowledgePage() {
  const toast = useToast()
  const qc = useQueryClient()
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)

  // Auto-update modal state
  const [showGapModal, setShowGapModal] = useState(false)
  const [gaps, setGaps] = useState<FAQGap[]>([])
  const [analyzingGaps, setAnalyzingGaps] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)

  // ── Queries ──────────────────────────────────────────────────────────────

  const { data: docs, isLoading } = useQuery({
    queryKey: ['knowledge'],
    queryFn: () => get<KnowledgeBase[]>('/knowledge/list'),
    refetchInterval: 5000,
  })

  // ── Mutations ─────────────────────────────────────────────────────────────

  const deleteMutation = useMutation({
    mutationFn: (id: string) => del(`/knowledge/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['knowledge'] })
      toast.success('Document deleted')
    },
    onError: (e) => toast.error('Failed to delete', (e as Error).message),
  })

  const autoUpdateMutation = useMutation({
    mutationFn: (approvedFaqs: FAQGap[]) =>
      post<{ message: string }>('/knowledge/auto-update', {
        approved_faqs: approvedFaqs.map(({ question, answer, source_count }) => ({
          question, answer, source_count,
        })),
      }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: ['knowledge'] })
      setShowGapModal(false)
      setGaps([])
      toast.success('Knowledge base updated!', res.message)
    },
    onError: (e) => toast.error('Update failed', (e as Error).message),
  })

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleUpload = useCallback(async (file: File) => {
    if (!file) return
    const allowed = [
      'application/pdf',
      'text/plain',
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    ]
    if (!allowed.includes(file.type)) {
      toast.error('Invalid file type', 'Only PDF, TXT, DOCX allowed')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error('File too large', 'Maximum 10MB allowed')
      return
    }
    setUploading(true)
    try {
      await uploadFile('/knowledge/upload', file)
      qc.invalidateQueries({ queryKey: ['knowledge'] })
      toast.success('Document uploaded', 'Training started...')
    } catch (e) {
      toast.error('Upload failed', (e as Error).message)
    } finally {
      setUploading(false)
    }
  }, [qc, toast])

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const file = e.dataTransfer.files[0]
    if (file) handleUpload(file)
  }, [handleUpload])

  const handleAnalyzeGaps = async () => {
    setAnalyzingGaps(true)
    setShowGapModal(true)
    try {
      const result = await get<FAQGap[]>('/knowledge/gaps')
      if (!result || result.length === 0) {
        toast.info('No gaps found', 'No escalated conversations today to learn from')
        setShowGapModal(false)
      } else {
        // All start as approved by default — owner can reject individually
        setGaps(result.map((g) => ({ ...g, approved: true })))
      }
    } catch (e) {
      toast.error('Analysis failed', (e as Error).message)
      setShowGapModal(false)
    } finally {
      setAnalyzingGaps(false)
    }
  }

  const toggleFAQ = (index: number) => {
    setGaps((prev) =>
      prev.map((g, i) => i === index ? { ...g, approved: !g.approved } : g)
    )
  }

  const handleApplyFAQs = () => {
    const approved = gaps.filter((g) => g.approved)
    if (approved.length === 0) {
      toast.warning('No FAQs selected', 'Approve at least one FAQ entry')
      return
    }
    autoUpdateMutation.mutate(approved)
  }

  const approvedCount = gaps.filter((g) => g.approved).length

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="p-6 max-w-4xl mx-auto">

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-[#F1F1F5]">Knowledge Base</h2>
          <p className="text-xs text-[#64748B] mt-0.5">
            Upload documents your AI uses to answer customer questions
          </p>
        </div>

        {/* Auto-update button */}
        <Button
          variant="secondary"
          size="sm"
          icon={<Sparkles size={14} />}
          onClick={handleAnalyzeGaps}
          loading={analyzingGaps}
        >
          Auto-Update KB
        </Button>
      </div>

      {/* Upload zone */}
      <label
        htmlFor="kb-file"
        onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={`flex flex-col items-center gap-4 p-10 rounded-xl border-2 border-dashed cursor-pointer transition-all duration-200 mb-6 ${
          dragging
            ? 'border-indigo-500 bg-indigo-500/10'
            : 'border-[#2A2A45] hover:border-indigo-500/50 hover:bg-indigo-500/5'
        }`}
      >
        <div className={`w-12 h-12 rounded-xl flex items-center justify-center transition-colors ${
          dragging ? 'bg-indigo-500/20' : 'bg-[#1E1E35]'
        }`}>
          {uploading
            ? <Clock size={22} className="text-indigo-400 animate-spin" />
            : <Upload size={22} className={dragging ? 'text-indigo-400' : 'text-[#64748B]'} />
          }
        </div>
        <div className="text-center">
          <p className="text-sm font-medium text-[#F1F1F5]">
            {uploading ? 'Uploading...' : 'Drop your file here or click to upload'}
          </p>
          <p className="text-xs text-[#4A4A6A] mt-1">PDF, TXT, DOCX — max 10MB</p>
        </div>
        <input
          id="kb-file"
          type="file"
          accept=".pdf,.txt,.docx"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
          disabled={uploading}
          aria-label="Upload knowledge base document"
        />
      </label>

      {/* Documents list */}
      <div className="space-y-3">
        <h3 className="text-sm font-semibold text-[#F1F1F5]">
          Uploaded Documents
          {docs && (
            <span className="text-[#4A4A6A] font-normal ml-2">({docs.length})</span>
          )}
        </h3>

        {isLoading ? (
          [...Array(3)].map((_, i) => (
            <div key={i} className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-4 flex gap-3">
              <div className="skeleton w-9 h-9 rounded-lg flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <div className="skeleton h-3 w-48 rounded" />
                <div className="skeleton h-2.5 w-32 rounded" />
              </div>
            </div>
          ))
        ) : !docs || docs.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-12 bg-[#16162A] border border-[#1E1E35] rounded-xl">
            <BookOpen size={24} className="text-[#2A2A45]" />
            <p className="text-sm text-[#4A4A6A]">No documents uploaded yet</p>
            <p className="text-xs text-[#4A4A6A]">Upload your FAQ or services document to train your AI</p>
          </div>
        ) : (
          <AnimatePresence>
            {docs.map((doc, i) => (
              <motion.div
                key={doc.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
                className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-4 flex items-center gap-3 hover:border-[#2A2A45] transition-colors"
              >
                <div className="w-9 h-9 rounded-lg bg-indigo-500/10 flex items-center justify-center flex-shrink-0">
                  <FileText size={16} className="text-indigo-400" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium text-[#F1F1F5] truncate">{doc.filename}</p>
                    {statusIcon[doc.training_status]}
                  </div>
                  <div className="flex items-center gap-3 mt-1 flex-wrap">
                    <StatusBadge status={doc.training_status} />
                    {doc.chunk_count > 0 && (
                      <span className="text-[10px] text-[#4A4A6A]">{doc.chunk_count} chunks</span>
                    )}
                    {doc.file_size && (
                      <span className="text-[10px] text-[#4A4A6A]">
                        {(doc.file_size / 1024).toFixed(0)} KB
                      </span>
                    )}
                    {doc.created_at && (
                      <span className="text-[10px] text-[#4A4A6A]">
                        {formatRelativeTime(doc.created_at)}
                      </span>
                    )}
                  </div>
                  {doc.training_error && (
                    <p className="text-[10px] text-red-400 mt-1">{doc.training_error}</p>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  icon={<Trash2 size={14} />}
                  onClick={() => deleteMutation.mutate(doc.id)}
                  loading={deleteMutation.isPending}
                  className="text-[#64748B] hover:text-red-400 flex-shrink-0"
                  aria-label={`Delete ${doc.filename}`}
                />
              </motion.div>
            ))}
          </AnimatePresence>
        )}
      </div>

      {/* ── Auto-Update Modal ─────────────────────────────────────────────── */}
      <Modal
        open={showGapModal}
        onClose={() => { setShowGapModal(false); setGaps([]) }}
        title="Auto-Update Knowledge Base"
        description="AI analysed today's escalated conversations and found these knowledge gaps"
        size="lg"
      >
        <div className="space-y-4">
          {analyzingGaps ? (
            <div className="flex flex-col items-center gap-4 py-8">
              <RefreshCw size={28} className="text-indigo-400 animate-spin" />
              <div className="text-center">
                <p className="text-sm font-medium text-[#F1F1F5]">Analysing today&apos;s conversations...</p>
                <p className="text-xs text-[#64748B] mt-1">Finding questions the AI could not answer</p>
              </div>
            </div>
          ) : gaps.length === 0 ? (
            <div className="flex flex-col items-center gap-3 py-8">
              <CheckCircle size={28} className="text-emerald-400" />
              <p className="text-sm text-[#F1F1F5]">No gaps found</p>
            </div>
          ) : (
            <>
              {/* Summary */}
              <div className="flex items-center justify-between p-3 rounded-lg bg-indigo-500/10 border border-indigo-500/20">
                <div className="flex items-center gap-2">
                  <Sparkles size={14} className="text-indigo-400" />
                  <span className="text-xs text-indigo-400 font-medium">
                    {gaps.length} gaps found · {approvedCount} selected
                  </span>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setGaps((g) => g.map((f) => ({ ...f, approved: true })))}
                    className="text-[10px] text-emerald-400 hover:text-emerald-300 transition-colors"
                  >
                    Select all
                  </button>
                  <span className="text-[#4A4A6A]">·</span>
                  <button
                    onClick={() => setGaps((g) => g.map((f) => ({ ...f, approved: false })))}
                    className="text-[10px] text-red-400 hover:text-red-300 transition-colors"
                  >
                    Deselect all
                  </button>
                </div>
              </div>

              {/* FAQ entries */}
              <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
                {gaps.map((faq, i) => (
                  <motion.div
                    key={i}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: i * 0.05 }}
                    className={`p-4 rounded-xl border transition-all duration-150 ${
                      faq.approved
                        ? 'border-indigo-500/30 bg-indigo-500/5'
                        : 'border-[#1E1E35] bg-[#111120] opacity-50'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-[#F1F1F5] mb-1">
                          Q: {faq.question}
                        </p>
                        {editingIndex === i ? (
                          <textarea
                            autoFocus
                            value={faq.answer}
                            onChange={(e) =>
                              setGaps((prev) =>
                                prev.map((g, idx) =>
                                  idx === i ? { ...g, answer: e.target.value } : g
                                )
                              )
                            }
                            onBlur={() => setEditingIndex(null)}
                            rows={3}
                            className="w-full mt-1 bg-[#0F0F1A] border border-indigo-500/40 rounded-lg px-2.5 py-2 text-xs text-[#F1F1F5] leading-relaxed outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
                          />
                        ) : (
                          <div className="flex items-start gap-1.5 group">
                            <p className="text-xs text-[#94A3B8] leading-relaxed flex-1">
                              A: {faq.answer}
                            </p>
                            <button
                              onClick={() => setEditingIndex(i)}
                              className="shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity text-[#4A4A6A] hover:text-indigo-400"
                              title="Edit answer"
                            >
                              <Pencil size={11} />
                            </button>
                          </div>
                        )}
                        {faq.source_count > 1 && (
                          <p className="text-[10px] text-[#4A4A6A] mt-1">
                            Asked {faq.source_count} times today
                          </p>
                        )}
                      </div>

                      {/* Approve/Reject toggle */}
                      <button
                        onClick={() => toggleFAQ(i)}
                        className={`flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center transition-all duration-150 ${
                          faq.approved
                            ? 'bg-emerald-500/10 text-emerald-400 hover:bg-red-500/10 hover:text-red-400'
                            : 'bg-red-500/10 text-red-400 hover:bg-emerald-500/10 hover:text-emerald-400'
                        }`}
                        title={faq.approved ? 'Click to reject' : 'Click to approve'}
                        aria-label={faq.approved ? 'Reject this FAQ' : 'Approve this FAQ'}
                      >
                        {faq.approved
                          ? <ThumbsUp size={14} />
                          : <ThumbsDown size={14} />
                        }
                      </button>
                    </div>
                  </motion.div>
                ))}
              </div>

              {/* Actions */}
              <div className="flex gap-3 justify-end pt-2 border-t border-[#1E1E35]">
                <Button
                  variant="secondary"
                  onClick={() => { setShowGapModal(false); setGaps([]) }}
                >
                  Cancel
                </Button>
                <Button
                  onClick={handleApplyFAQs}
                  loading={autoUpdateMutation.isPending}
                  disabled={approvedCount === 0}
                  icon={<CheckCircle size={14} />}
                >
                  Apply {approvedCount} FAQ{approvedCount !== 1 ? 's' : ''} to KB
                </Button>
              </div>
            </>
          )}
        </div>
      </Modal>
    </div>
  )
}