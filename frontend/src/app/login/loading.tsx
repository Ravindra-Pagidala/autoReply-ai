import { Zap } from 'lucide-react'

export default function LoginLoading() {
  return (
    <div className="min-h-screen bg-[#0F0F1A] flex items-center justify-center">
      <div className="flex flex-col items-center gap-4">
        <div className="w-12 h-12 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center animate-pulse">
          <Zap size={22} className="text-indigo-400" />
        </div>
        <p className="text-xs text-[#64748B]">Loading...</p>
      </div>
    </div>
  )
}