'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { Sidebar } from '@/components/layout/Sidebar'
import { TopBar } from '@/components/layout/TopBar'
import { useAuthStore } from '@/store/auth.store'
import { useUIStore } from '@/store/ui.store'
import { useRealtime } from '@/hooks/useRealtime'
import { supabase } from '@/lib/supabase'
import { get } from '@/lib/api'
import type { BusinessProfile } from '@/types'

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const router = useRouter()
  const { user, setUser, setProfile, setLoading, logout } = useAuthStore()
  const { sidebarCollapsed } = useUIStore()

  // Realtime subscriptions — live updates across all pages
  useRealtime()

  useEffect(() => {
    const initAuth = async () => {
      setLoading(true)

      const { data: { session } } = await supabase.auth.getSession()

      if (!session) {
        logout()
        router.replace('/login')
        return
      }

      setUser({
        id: session.user.id,
        email: session.user.email ?? '',
        token: session.access_token,
      })

      try {
        const res = await get<{ user: unknown; profile: BusinessProfile | null }>('/auth/me')
        if (res.profile) {
          setProfile(res.profile)
          if (!res.profile.onboarding_completed) {
            router.replace('/onboarding')
            return
          }
        } else {
          router.replace('/onboarding')
          return
        }
      } catch {
        // Profile load failed — still show dashboard
      } finally {
        setLoading(false)
      }
    }

    initAuth()

    // Listen for auth state changes
    const { data: { subscription } } = supabase.auth.onAuthStateChange(
      (_event, session) => {
        if (!session) {
          logout()
          router.replace('/login')
        }
      }
    )

    return () => subscription.unsubscribe()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  if (!user) return null

  return (
    <div className="min-h-screen bg-[#0F0F1A]">
      <Sidebar />
      <TopBar />
      <motion.main
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.2, ease: 'easeOut' }}
        className="transition-all duration-200 pt-14 min-h-screen"
        style={{ marginLeft: sidebarCollapsed ? 56 : 240 }}
      >
        {children}
      </motion.main>
    </div>
  )
}