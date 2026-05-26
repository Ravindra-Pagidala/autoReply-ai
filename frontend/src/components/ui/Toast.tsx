'use client'

import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle, XCircle, AlertTriangle, Info, X } from 'lucide-react'
import { useUIStore } from '@/store/ui.store'
import { toastVariants } from '@/lib/animations'
import { cn } from '@/lib/utils'

const icons = {
  success: <CheckCircle size={16} className="text-emerald-400 flex-shrink-0" />,
  error:   <XCircle size={16} className="text-red-400 flex-shrink-0" />,
  warning: <AlertTriangle size={16} className="text-amber-400 flex-shrink-0" />,
  info:    <Info size={16} className="text-indigo-400 flex-shrink-0" />,
}

const borderColors = {
  success: 'border-l-emerald-500',
  error:   'border-l-red-500',
  warning: 'border-l-amber-500',
  info:    'border-l-indigo-500',
}

export function Toast() {
  const { toasts, removeToast } = useUIStore()

  return (
    <div
      className="fixed top-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none"
      aria-live="polite"
      aria-label="Notifications"
    >
      <AnimatePresence mode="popLayout">
        {toasts.map((toast) => (
          <motion.div
            key={toast.id}
            variants={toastVariants}
            initial="initial"
            animate="animate"
            exit="exit"
            layout
            className={cn(
              'pointer-events-auto flex items-start gap-3',
              'bg-[#16162A] border border-[#2A2A45] border-l-2',
              'rounded-xl p-4 shadow-xl max-w-sm w-full',
              borderColors[toast.type]
            )}
            role="alert"
          >
            {icons[toast.type]}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-[#F1F1F5] leading-snug">
                {toast.title}
              </p>
              {toast.message && (
                <p className="text-xs text-[#64748B] mt-0.5 leading-snug">
                  {toast.message}
                </p>
              )}
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              className="text-[#4A4A6A] hover:text-[#F1F1F5] transition-colors flex-shrink-0"
              aria-label="Dismiss notification"
            >
              <X size={14} />
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

export function useToast() {
  const addToast = useUIStore((s) => s.addToast)
  return {
    success: (title: string, message?: string) =>
      addToast({ type: 'success', title, message }),
    error: (title: string, message?: string) =>
      addToast({ type: 'error', title, message }),
    warning: (title: string, message?: string) =>
      addToast({ type: 'warning', title, message }),
    info: (title: string, message?: string) =>
      addToast({ type: 'info', title, message }),
  }
}