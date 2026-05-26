import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User, BusinessProfile } from '@/types'

interface AuthState {
  user: User | null
  profile: BusinessProfile | null
  isLoading: boolean
  setUser: (user: User | null) => void
  setProfile: (profile: BusinessProfile | null) => void
  setLoading: (loading: boolean) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      profile: null,
      isLoading: true,

      setUser: (user) => {
        set({ user })
        if (user?.token && typeof window !== 'undefined') {
          localStorage.setItem('access_token', user.token)
        }
      },

      setProfile: (profile) => set({ profile }),

      setLoading: (isLoading) => set({ isLoading }),

      logout: () => {
        if (typeof window !== 'undefined') {
          localStorage.removeItem('access_token')
        }
        set({ user: null, profile: null })
      },
    }),
    {
      name: 'autoreply-auth',
      partialize: (state) => ({
        user: state.user,
        profile: state.profile,
      }),
    }
  )
)