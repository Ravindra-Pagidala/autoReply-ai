'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { Zap, Building2, Plug, BookOpen, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/Button'
import { Input, Textarea } from '@/components/ui/Input'
import { Toggle } from '@/components/ui/Toggle'
import { useToast } from '@/components/ui/Toast'
import { useAuthStore } from '@/store/auth.store'
import { post, patch, uploadFile } from '@/lib/api'
import { fadeInUp } from '@/lib/animations'
import type { BusinessProfile } from '@/types'

const STEPS = [
  { id: 1, label: 'Profile',  icon: Building2 },
  { id: 2, label: 'Channels', icon: Plug },
  { id: 3, label: 'Knowledge',icon: BookOpen },
  { id: 4, label: 'Done',     icon: CheckCircle },
]

const INDUSTRIES = [
  'Salon & Beauty', 'Coaching & Training', 'Retail', 'Healthcare',
  'Real Estate', 'Restaurant & Food', 'Finance', 'Education',
  'Fitness', 'Technology', 'Legal', 'Other',
]

const TONES = ['professional', 'friendly', 'casual'] as const
const LANGUAGES = ['english', 'hindi', 'telugu'] as const

export default function OnboardingPage() {
  const router = useRouter()
  const toast = useToast()
  const { setProfile } = useAuthStore()

  const [step, setStep] = useState(1)
  const [loading, setLoading] = useState(false)

  // Step 1 — Profile
  const [businessName, setBusinessName] = useState('')
  const [industry, setIndustry] = useState('')
  const [description, setDescription] = useState('')
  const [botTone, setBotTone] = useState<'professional' | 'friendly' | 'casual'>('professional')
  const [botLanguage, setBotLanguage] = useState<'english' | 'hindi' | 'telugu'>('english')

  // Step 2 — Channels
  const [whatsappNumber, setWhatsappNumber] = useState('')
  const [phoneNumber, setPhoneNumber] = useState('')
  const [businessEmail, setBusinessEmail] = useState('')

  // Step 3 — KB
  const [kbFile, setKbFile] = useState<File | null>(null)
  const [kbUploaded, setKbUploaded] = useState(false)

  const handleStep1 = async () => {
    if (!businessName || !industry) {
      toast.error('Please fill in business name and industry')
      return
    }
    setLoading(true)
    try {
      const profile = await post<BusinessProfile>('/auth/profile', {
        business_name: businessName,
        industry,
        description,
        bot_tone: botTone,
        bot_language: botLanguage,
      })
      setProfile(profile)
      setStep(2)
    } catch (e) {
      toast.error('Failed to save profile', (e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleStep2 = async () => {
    setLoading(true)
    try {
      const profile = await patch<BusinessProfile>('/auth/profile', {
        whatsapp_number: whatsappNumber || null,
        phone_number: phoneNumber || null,
        business_email: businessEmail || null,
        onboarding_step: 3,
      })
      setProfile(profile)
      setStep(3)
    } catch (e) {
      toast.error('Failed to save channels', (e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  const handleStep3 = async () => {
    if (kbFile) {
      setLoading(true)
      try {
        await uploadFile('/knowledge/upload', kbFile)
        setKbUploaded(true)
        toast.success('Knowledge base uploaded!')
      } catch (e) {
        toast.error('Upload failed', (e as Error).message)
        setLoading(false)
        return
      }
      setLoading(false)
    }
    setStep(4)
  }

  const handleComplete = async () => {
    setLoading(true)
    try {
      await post('/auth/profile/complete-onboarding', {})
      const profile = await patch<BusinessProfile>('/auth/profile', {
        onboarding_completed: true,
      })
      setProfile(profile)
      toast.success('Setup complete! Welcome to AutoReply AI')
      router.replace('/dashboard')
    } catch (e) {
      toast.error('Failed to complete setup', (e as Error).message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0F0F1A] flex items-center justify-center p-4">
      <div
        className="absolute inset-0 pointer-events-none"
        aria-hidden="true"
        style={{
          background: 'radial-gradient(ellipse 60% 50% at 50% 30%, rgba(99,102,241,0.05) 0%, transparent 70%)',
        }}
      />

      <div className="w-full max-w-lg relative z-10">
        {/* Header */}
        <div className="flex items-center gap-3 mb-8">
          <div className="w-9 h-9 rounded-lg bg-indigo-500 flex items-center justify-center">
            <Zap size={18} className="text-white" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-[#F1F1F5]">AutoReply AI</h1>
            <p className="text-xs text-[#64748B]">Setup your workspace</p>
          </div>
        </div>

        {/* Step indicators */}
        <div className="flex items-center gap-2 mb-8">
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex items-center gap-2 flex-1">
              <div className="flex items-center gap-2">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold transition-colors duration-200 ${
                  step > s.id
                    ? 'bg-indigo-500 text-white'
                    : step === s.id
                    ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500'
                    : 'bg-[#1E1E35] text-[#4A4A6A]'
                }`}>
                  {step > s.id ? <CheckCircle size={14} /> : s.id}
                </div>
                <span className={`text-xs font-medium hidden sm:block ${
                  step >= s.id ? 'text-[#F1F1F5]' : 'text-[#4A4A6A]'
                }`}>
                  {s.label}
                </span>
              </div>
              {i < STEPS.length - 1 && (
                <div className={`flex-1 h-px mx-2 transition-colors duration-300 ${
                  step > s.id ? 'bg-indigo-500' : 'bg-[#1E1E35]'
                }`} />
              )}
            </div>
          ))}
        </div>

        {/* Card */}
        <div className="bg-[#16162A] border border-[#1E1E35] rounded-2xl overflow-hidden shadow-2xl">
          <AnimatePresence mode="wait">
            {/* Step 1 — Business Profile */}
            {step === 1 && (
              <motion.div
                key="step1"
                variants={fadeInUp}
                initial="initial"
                animate="animate"
                exit="exit"
                className="p-6 space-y-4"
              >
                <div>
                  <h2 className="text-base font-semibold text-[#F1F1F5]">Business Profile</h2>
                  <p className="text-xs text-[#64748B] mt-0.5">Tell us about your business</p>
                </div>

                <Input
                  label="Business Name"
                  placeholder="e.g. Priya's Salon"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  required
                />

                <div className="flex flex-col gap-1.5">
                  <label className="text-xs font-medium text-[#94A3B8]">Industry <span className="text-red-400">*</span></label>
                  <select
                    value={industry}
                    onChange={(e) => setIndustry(e.target.value)}
                    className="w-full h-10 rounded-lg text-sm text-[#F1F1F5] bg-[#111120] border border-[#1E1E35] px-3 outline-none focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 transition-all"
                  >
                    <option value="" className="bg-[#111120]">Select industry...</option>
                    {INDUSTRIES.map((i) => (
                      <option key={i} value={i} className="bg-[#111120]">{i}</option>
                    ))}
                  </select>
                </div>

                <Textarea
                  label="Description"
                  placeholder="What does your business do?"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                />

                {/* Bot tone */}
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-medium text-[#94A3B8]">Bot Tone</label>
                  <div className="flex gap-2">
                    {TONES.map((t) => (
                      <button
                        key={t}
                        type="button"
                        onClick={() => setBotTone(t)}
                        className={`flex-1 h-9 rounded-lg text-xs font-medium capitalize transition-all duration-150 ${
                          botTone === t
                            ? 'bg-indigo-500 text-white'
                            : 'bg-[#111120] text-[#64748B] border border-[#1E1E35] hover:border-indigo-500/50'
                        }`}
                      >
                        {t}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Language */}
                <div className="flex flex-col gap-2">
                  <label className="text-xs font-medium text-[#94A3B8]">Bot Language</label>
                  <div className="flex gap-2">
                    {LANGUAGES.map((l) => (
                      <button
                        key={l}
                        type="button"
                        onClick={() => setBotLanguage(l)}
                        className={`flex-1 h-9 rounded-lg text-xs font-medium capitalize transition-all duration-150 ${
                          botLanguage === l
                            ? 'bg-indigo-500 text-white'
                            : 'bg-[#111120] text-[#64748B] border border-[#1E1E35] hover:border-indigo-500/50'
                        }`}
                      >
                        {l}
                      </button>
                    ))}
                  </div>
                </div>

                <Button className="w-full" onClick={handleStep1} loading={loading}>
                  Continue →
                </Button>
              </motion.div>
            )}

            {/* Step 2 — Channels */}
            {step === 2 && (
              <motion.div
                key="step2"
                variants={fadeInUp}
                initial="initial"
                animate="animate"
                exit="exit"
                className="p-6 space-y-4"
              >
                <div>
                  <h2 className="text-base font-semibold text-[#F1F1F5]">Connect Channels</h2>
                  <p className="text-xs text-[#64748B] mt-0.5">All fields are optional — connect later from settings</p>
                </div>

                <Input
                  label="WhatsApp Number"
                  placeholder="+91 98765 43210"
                  value={whatsappNumber}
                  onChange={(e) => setWhatsappNumber(e.target.value)}
                  hint="The number customers will message"
                />
                <Input
                  label="Business Phone"
                  placeholder="+91 98765 43210"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  hint="For voice call automation"
                />
                <Input
                  label="Business Email"
                  type="email"
                  placeholder="hello@mybusiness.com"
                  value={businessEmail}
                  onChange={(e) => setBusinessEmail(e.target.value)}
                  hint="For email auto-reply"
                />

                <div className="flex gap-3">
                  <Button variant="secondary" className="flex-1" onClick={() => setStep(1)}>
                    ← Back
                  </Button>
                  <Button className="flex-1" onClick={handleStep2} loading={loading}>
                    Continue →
                  </Button>
                </div>
              </motion.div>
            )}

            {/* Step 3 — Knowledge Base */}
            {step === 3 && (
              <motion.div
                key="step3"
                variants={fadeInUp}
                initial="initial"
                animate="animate"
                exit="exit"
                className="p-6 space-y-4"
              >
                <div>
                  <h2 className="text-base font-semibold text-[#F1F1F5]">Knowledge Base</h2>
                  <p className="text-xs text-[#64748B] mt-0.5">Upload your FAQ, pricing, or services document</p>
                </div>

                <label
                  htmlFor="kb-upload"
                  className={`flex flex-col items-center gap-3 p-6 rounded-xl border-2 border-dashed cursor-pointer transition-all duration-150 ${
                    kbFile
                      ? 'border-indigo-500 bg-indigo-500/5'
                      : 'border-[#2A2A45] hover:border-indigo-500/50 hover:bg-indigo-500/5'
                  }`}
                >
                  <BookOpen size={28} className={kbFile ? 'text-indigo-400' : 'text-[#4A4A6A]'} />
                  {kbFile ? (
                    <div className="text-center">
                      <p className="text-sm font-medium text-indigo-400">{kbFile.name}</p>
                      <p className="text-xs text-[#64748B]">{(kbFile.size / 1024).toFixed(0)} KB</p>
                    </div>
                  ) : (
                    <div className="text-center">
                      <p className="text-sm text-[#94A3B8]">Click to upload or drag and drop</p>
                      <p className="text-xs text-[#4A4A6A] mt-1">PDF, TXT, DOCX up to 10MB</p>
                    </div>
                  )}
                  <input
                    id="kb-upload"
                    type="file"
                    accept=".pdf,.txt,.docx"
                    className="hidden"
                    onChange={(e) => setKbFile(e.target.files?.[0] ?? null)}
                    aria-label="Upload knowledge base document"
                  />
                </label>

                {kbUploaded && (
                  <div className="flex items-center gap-2 p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                    <CheckCircle size={14} className="text-emerald-400" />
                    <p className="text-xs text-emerald-400">Document uploaded and training started</p>
                  </div>
                )}

                <div className="flex gap-3">
                  <Button variant="secondary" className="flex-1" onClick={() => setStep(2)}>
                    ← Back
                  </Button>
                  <Button className="flex-1" onClick={handleStep3} loading={loading}>
                    {kbFile ? 'Upload & Continue →' : 'Skip for now →'}
                  </Button>
                </div>
              </motion.div>
            )}

            {/* Step 4 — Done */}
            {step === 4 && (
              <motion.div
                key="step4"
                variants={fadeInUp}
                initial="initial"
                animate="animate"
                exit="exit"
                className="p-6 text-center space-y-4"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.1 }}
                  className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mx-auto"
                >
                  <CheckCircle size={32} className="text-emerald-400" />
                </motion.div>
                <div>
                  <h2 className="text-base font-semibold text-[#F1F1F5]">You&apos;re all set!</h2>
                  <p className="text-xs text-[#64748B] mt-1">
                    Your AI bot is ready. Go to the dashboard to monitor conversations.
                  </p>
                </div>
                <Button className="w-full" onClick={handleComplete} loading={loading}>
                  Go to Dashboard →
                </Button>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </div>
  )
}