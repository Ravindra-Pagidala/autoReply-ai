'use client'

import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'
import { useAuthStore } from '@/store/auth.store'
import { useUIStore } from '@/store/ui.store'

/**
 * useRealtime — subscribes to Supabase realtime channels.
 * Call once at the dashboard layout level.
 * Automatically invalidates TanStack Query cache on new events
 * so all pages update live without polling.
 *
 * Tables subscribed:
 *  - conversations → invalidates inbox + dashboard stats
 *  - leads         → invalidates leads + dashboard stats
 *  - escalations   → invalidates escalations + dashboard stats + toast
 *  - notifications → invalidates notifications + updates unread badge
 */
export function useRealtime() {
  const qc = useQueryClient()
  const { user } = useAuthStore()
  const { addToast } = useUIStore()

  useEffect(() => {
    if (!user?.id) return

    const userId = user.id

    // Conversations channel
    const conversationChannel = supabase
      .channel(`conversations:${userId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'conversations',
          filter: `user_id=eq.${userId}`,
        },
        () => {
          qc.invalidateQueries({ queryKey: ['conversations'] })
          qc.invalidateQueries({ queryKey: ['conversations-feed'] })
          qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
        }
      )
      .subscribe()

    // Leads channel
    const leadsChannel = supabase
      .channel(`leads:${userId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'leads',
          filter: `user_id=eq.${userId}`,
        },
        () => {
          qc.invalidateQueries({ queryKey: ['leads'] })
          qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
        }
      )
      .subscribe()

    // Escalations channel — also shows toast
    const escalationsChannel = supabase
      .channel(`escalations:${userId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'escalations',
          filter: `user_id=eq.${userId}`,
        },
        (payload) => {
          qc.invalidateQueries({ queryKey: ['escalations'] })
          qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
          addToast({
            type: 'warning',
            title: 'New Escalation',
            message: `A customer needs human assistance via ${(payload.new as { channel?: string })?.channel ?? 'unknown channel'}`,
          })
        }
      )
      .subscribe()

    // Notifications channel — updates bell badge
    const notificationsChannel = supabase
      .channel(`notifications:${userId}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'notifications',
          filter: `user_id=eq.${userId}`,
        },
        () => {
          qc.invalidateQueries({ queryKey: ['dashboard-stats'] })
        }
      )
      .subscribe()

    return () => {
      supabase.removeChannel(conversationChannel)
      supabase.removeChannel(leadsChannel)
      supabase.removeChannel(escalationsChannel)
      supabase.removeChannel(notificationsChannel)
    }
  }, [user?.id, qc, addToast])
}