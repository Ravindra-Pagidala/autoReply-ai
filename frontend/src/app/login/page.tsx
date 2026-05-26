'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { Zap, Mail, Lock, AlertCircle } from 'lucide-react'
import type { Metadata } from 'next'
import { supabase } from '@/lib/supabase'
import { useAuthStore } from '@/store/auth.store'
import { get } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { fadeInUp, staggerContainer, staggerItem } from '@/lib/animations'
import type { BusinessProfile } from '@/types'

export default function LoginPage() {
  const router = useRouter()
  const { setUser, setProfile } = useAuthStore()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)

  const handleGoogleLogin = async () => {
    setGoogleLoading(true)
    setError('')
    const { error: err } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: `${window.location.origin}/dashboard` },
    })
    if (err) {
      setError(err.message)
      setGoogleLoading(false)
    }
  }

  const handleEmailLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      setError('Please enter your email and password')
      return
    }
    setLoading(true)
    setError('')

    const { data, error: err } = await supabase.auth.signInWithPassword({
      email,
      password,
    })

    if (err) {
      setError(err.message)
      setLoading(false)
      return
    }

    if (data.session) {
      setUser({
        id: data.session.user.id,
        email: data.session.user.email ?? '',
        token: data.session.access_token,
      })

      try {
        const res = await get<{ user: unknown; profile: BusinessProfile | null }>('/auth/me')
        if (res.profile) {
          setProfile(res.profile)
          router.replace(res.profile.onboarding_completed ? '/dashboard' : '/onboarding')
        } else {
          router.replace('/onboarding')
        }
      } catch {
        router.replace('/onboarding')
      }
    }
    setLoading(false)
  }

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!email || !password) {
      setError('Please enter your email and password')
      return
    }
    setLoading(true)
    setError('')
    const { error: err } = await supabase.auth.signUp({ email, password })
    if (err) {
      setError(err.message)
    } else {
      setError('')
      alert('Check your email to confirm your account!')
    }
    setLoading(false)
  }

  return (
    <div className="min-h-screen bg-[#0F0F1A] flex items-center justify-center p-4 relative overflow-hidden">
      {/* Background glow */}
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden="true"
        style={{
          background: 'radial-gradient(ellipse 60% 50% at 50% 40%, rgba(99,102,241,0.06) 0%, transparent 70%)',
        }}
      />

      {/* Grid dots */}
      <div
        className="absolute inset-0 pointer-events-none opacity-30"
        aria-hidden="true"
        style={{
          backgroundImage: 'radial-gradient(circle, #1E1E35 1px, transparent 1px)',
          backgroundSize: '24px 24px',
        }}
      />

      <motion.div
        variants={staggerContainer}
        initial="initial"
        animate="animate"
        className="w-full max-w-sm relative z-10"
      >
        {/* Logo */}
        <motion.div variants={staggerItem} className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-indigo-500 flex items-center justify-center mb-4 shadow-lg shadow-indigo-500/20">
            <Zap size={22} className="text-white" />
          </div>
          <h1 className="text-xl font-bold text-[#F1F1F5]">AutoReply AI</h1>
          <p className="text-sm text-[#64748B] mt-1">Sign in to your workspace</p>
        </motion.div>

        {/* Card */}
        <motion.div
          variants={staggerItem}
          className="bg-[#16162A] border border-[#1E1E35] rounded-2xl p-6 shadow-2xl"
        >
          {/* Google button */}
          <Button
            variant="secondary"
            className="w-full mb-5 h-10"
            onClick={handleGoogleLogin}
            loading={googleLoading}
            icon={
              <svg width="16" height="16" viewBox="0 0 24 24" aria-hidden="true">
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
            }
          >
            Continue with Google
          </Button>

          {/* Divider */}
          <div className="flex items-center gap-3 mb-5">
            <div className="flex-1 h-px bg-[#1E1E35]" />
            <span className="text-xs text-[#4A4A6A]">or</span>
            <div className="flex-1 h-px bg-[#1E1E35]" />
          </div>

          {/* Email form */}
          <form onSubmit={handleEmailLogin} className="space-y-4" noValidate>
            <Input
              label="Email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              leftIcon={<Mail size={14} />}
              autoComplete="email"
              required
            />
            <Input
              label="Password"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              leftIcon={<Lock size={14} />}
              autoComplete="current-password"
              required
            />

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-2 p-3 rounded-lg bg-red-500/10 border border-red-500/20"
                role="alert"
              >
                <AlertCircle size={14} className="text-red-400 flex-shrink-0" />
                <p className="text-xs text-red-400">{error}</p>
              </motion.div>
            )}

            <Button
              type="submit"
              variant="primary"
              className="w-full"
              loading={loading}
            >
              Sign In
            </Button>

            <Button
              type="button"
              variant="ghost"
              className="w-full text-xs"
              onClick={handleSignUp}
              loading={loading}
            >
              Don&apos;t have an account? Sign up
            </Button>
          </form>
        </motion.div>
      </motion.div>
    </div>
  )
}