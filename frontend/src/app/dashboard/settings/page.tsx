'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Save, Bot, Clock, Phone } from 'lucide-react'
import { get, patch } from '@/lib/api'
import { Button } from '@/components/ui/Button'
import { Input } from '@/components/ui/Input'
import { Toggle } from '@/components/ui/Toggle'
import { useToast } from '@/components/ui/Toast'
import { useAuthStore } from '@/store/auth.store'
import type { BusinessProfile } from '@/types'

const TONES = ['professional', 'friendly', 'casual'] as const
const LANGUAGES = ['english', 'hindi', 'telugu'] as const

interface SettingsForm {
  business_name: string
  industry: string
  description: string
  whatsapp_number: string
  phone_number: string
  business_email: string
  bot_tone: string
  bot_language: string
  fallback_message: string
  working_hours_start: string
  working_hours_end: string
  working_days: string
  escalation_threshold: number
  bot_active: boolean
}

const DEFAULT_FORM: SettingsForm = {
  business_name: '', industry: '', description: '',
  whatsapp_number: '', phone_number: '', business_email: '',
  bot_tone: 'professional', bot_language: 'english',
  fallback_message: '', working_hours_start: '09:00',
  working_hours_end: '18:00', working_days: 'Mon-Sat',
  escalation_threshold: 2, bot_active: true,
}

function profileToForm(p: BusinessProfile): SettingsForm {
  return {
    business_name:       p.business_name ?? '',
    industry:            p.industry ?? '',
    description:         p.description ?? '',
    whatsapp_number:     p.whatsapp_number ?? '',
    phone_number:        p.phone_number ?? '',
    business_email:      p.business_email ?? '',
    bot_tone:            p.bot_tone ?? 'professional',
    bot_language:        p.bot_language ?? 'english',
    fallback_message:    p.fallback_message ?? '',
    working_hours_start: p.working_hours_start ?? '09:00',
    working_hours_end:   p.working_hours_end ?? '18:00',
    working_days:        p.working_days ?? 'Mon-Sat',
    escalation_threshold: p.escalation_threshold ?? 2,
    bot_active:          p.bot_active ?? true,
  }
}

export default function SettingsPage() {
  const toast = useToast()
  const qc = useQueryClient()
  const { setProfile } = useAuthStore()

  // form is initialized from DEFAULT_FORM
  // updated once via useState initializer when profile loads
  const [form, setForm] = useState<SettingsForm>(DEFAULT_FORM)
  const [hydrated, setHydrated] = useState(false)

  const { isLoading } = useQuery({
    queryKey: ['profile-settings'],
    queryFn: async () => {
      const res = await get<{ user: unknown; profile: BusinessProfile }>('/auth/me')
      return res.profile
    },
    // onSuccess is called outside render — safe to setState here
    // This is the React-recommended pattern for syncing external data
    staleTime: Infinity,
    select: (profile) => profile,
    // Use the returned data via the query directly
  })

  // Separate query just to hydrate form — fires once
  useQuery({
    queryKey: ['profile-settings-hydrate'],
    queryFn: async () => {
      const res = await get<{ user: unknown; profile: BusinessProfile }>('/auth/me')
      return res.profile
    },
    enabled: !hydrated,
    staleTime: Infinity,
    // react-query calls this outside render cycle — safe
    select: (p) => {
      if (p && !hydrated) {
        // scheduled via queueMicrotask to avoid sync setState in render
        queueMicrotask(() => {
          setForm(profileToForm(p))
          setHydrated(true)
        })
      }
      return p
    },
  })

  const setField = <K extends keyof SettingsForm>(key: K, value: SettingsForm[K]) =>
    setForm((f) => ({ ...f, [key]: value }))

  const saveMutation = useMutation({
    mutationFn: () => patch<BusinessProfile>('/auth/profile', form),
    onSuccess: (updated) => {
      setProfile(updated)
      setForm(profileToForm(updated))
      qc.invalidateQueries({ queryKey: ['profile'] })
      toast.success('Settings saved')
    },
    onError: (e) => toast.error('Failed to save', (e as Error).message),
  })

  if (isLoading && !hydrated) {
    return (
      <div className="p-6 max-w-3xl mx-auto space-y-4">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5">
            <div className="skeleton h-4 w-32 mb-4 rounded" />
            <div className="space-y-3">
              <div className="skeleton h-10 rounded-lg" />
              <div className="skeleton h-10 rounded-lg" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-[#F1F1F5]">Settings</h2>
          <p className="text-xs text-[#64748B] mt-0.5">Configure your bot and business profile</p>
        </div>
        <Button icon={<Save size={14} />} onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
          Save Changes
        </Button>
      </div>

      {/* Bot Control */}
      <section className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5">
        <div className="flex items-center gap-2 mb-4">
          <Bot size={16} className="text-indigo-400" />
          <h3 className="text-sm font-semibold text-[#F1F1F5]">Bot Control</h3>
        </div>
        <Toggle
          checked={form.bot_active}
          onChange={(v) => setField('bot_active', v)}
          label="Bot Active"
          description="When enabled, your AI bot automatically handles incoming messages"
        />
      </section>

      {/* Business Info */}
      <section className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-[#F1F1F5]">Business Information</h3>
        <div className="grid grid-cols-2 gap-4">
          <Input label="Business Name" value={form.business_name}
            onChange={(e) => setField('business_name', e.target.value)} placeholder="My Business" />
          <Input label="Industry" value={form.industry}
            onChange={(e) => setField('industry', e.target.value)} placeholder="e.g. Salon & Beauty" />
        </div>
        <Input label="Description" value={form.description}
          onChange={(e) => setField('description', e.target.value)} placeholder="What does your business do?" />
        <Input label="Fallback Message" value={form.fallback_message}
          onChange={(e) => setField('fallback_message', e.target.value)}
          placeholder="I'll connect you with our team shortly."
          hint="Shown when AI cannot answer" />
      </section>

      {/* Channels */}
      <section className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2 mb-1">
          <Phone size={16} className="text-indigo-400" />
          <h3 className="text-sm font-semibold text-[#F1F1F5]">Channel Numbers</h3>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Input label="WhatsApp Number" value={form.whatsapp_number}
            onChange={(e) => setField('whatsapp_number', e.target.value)} placeholder="+91 98765 43210" />
          <Input label="Phone Number" value={form.phone_number}
            onChange={(e) => setField('phone_number', e.target.value)} placeholder="+91 98765 43210" />
          <Input label="Business Email" type="email" value={form.business_email}
            onChange={(e) => setField('business_email', e.target.value)} placeholder="hello@business.com" />
        </div>
      </section>

      {/* Bot Personality */}
      <section className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-[#F1F1F5]">Bot Personality</h3>
        <div>
          <label className="text-xs font-medium text-[#94A3B8] block mb-2">Tone</label>
          <div className="flex gap-2">
            {TONES.map((t) => (
              <button key={t} type="button" onClick={() => setField('bot_tone', t)}
                className={`flex-1 h-9 rounded-lg text-xs font-medium capitalize transition-all ${
                  form.bot_tone === t
                    ? 'bg-indigo-500 text-white'
                    : 'bg-[#111120] text-[#64748B] border border-[#1E1E35] hover:border-indigo-500/50'
                }`}>{t}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="text-xs font-medium text-[#94A3B8] block mb-2">Language</label>
          <div className="flex gap-2">
            {LANGUAGES.map((l) => (
              <button key={l} type="button" onClick={() => setField('bot_language', l)}
                className={`flex-1 h-9 rounded-lg text-xs font-medium capitalize transition-all ${
                  form.bot_language === l
                    ? 'bg-indigo-500 text-white'
                    : 'bg-[#111120] text-[#64748B] border border-[#1E1E35] hover:border-indigo-500/50'
                }`}>{l}
              </button>
            ))}
          </div>
        </div>
        <div>
          <label className="text-xs font-medium text-[#94A3B8] block mb-2">
            Escalation threshold:{' '}
            <span className="text-indigo-400">{form.escalation_threshold} retries</span>
          </label>
          <input type="range" min="1" max="5" step="1"
            value={form.escalation_threshold}
            onChange={(e) => setField('escalation_threshold', Number(e.target.value))}
            className="w-full accent-indigo-500" aria-label="Escalation threshold" />
        </div>
      </section>

      {/* Working Hours */}
      <section className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5 space-y-4">
        <div className="flex items-center gap-2 mb-1">
          <Clock size={16} className="text-indigo-400" />
          <h3 className="text-sm font-semibold text-[#F1F1F5]">Working Hours</h3>
        </div>
        <div className="grid grid-cols-3 gap-4">
          <Input label="Opens at" type="time" value={form.working_hours_start}
            onChange={(e) => setField('working_hours_start', e.target.value)} />
          <Input label="Closes at" type="time" value={form.working_hours_end}
            onChange={(e) => setField('working_hours_end', e.target.value)} />
          <Input label="Working Days" value={form.working_days}
            onChange={(e) => setField('working_days', e.target.value)} placeholder="Mon-Sat" />
        </div>
      </section>

      <div className="flex justify-end pb-6">
        <Button icon={<Save size={14} />} onClick={() => saveMutation.mutate()} loading={saveMutation.isPending}>
          Save All Changes
        </Button>
      </div>
    </div>
  )
}