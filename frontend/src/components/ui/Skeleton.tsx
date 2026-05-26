import { cn } from '@/lib/utils'

interface SkeletonProps {
  className?: string
  width?: string | number
  height?: string | number
}

export function Skeleton({ className, width, height }: SkeletonProps) {
  return (
    <div
      className={cn('skeleton rounded-lg', className)}
      style={{ width, height }}
      aria-hidden="true"
    />
  )
}

export function StatsCardSkeleton() {
  return (
    <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5">
      <Skeleton className="h-3 w-24 mb-3" />
      <Skeleton className="h-8 w-16 mb-2" />
      <Skeleton className="h-2 w-12" />
    </div>
  )
}

export function ConversationSkeleton() {
  return (
    <div className="flex items-start gap-3 p-3">
      <Skeleton className="w-9 h-9 rounded-full flex-shrink-0" />
      <div className="flex-1 space-y-2">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-3 w-48" />
      </div>
      <Skeleton className="h-3 w-10" />
    </div>
  )
}

export function TableRowSkeleton({ cols = 5 }: { cols?: number }) {
  const widths = ['60%', '80%', '70%', '65%', '75%']
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <Skeleton className="h-4" width={widths[i % widths.length]} />
        </td>
      ))}
    </tr>
  )
}

export function PageSkeleton() {
  return (
    <div className="p-6 space-y-6" aria-label="Loading..." aria-busy="true">
      <div className="grid grid-cols-4 gap-4">
        {[...Array(4)].map((_, i) => <StatsCardSkeleton key={i} />)}
      </div>
      <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5 space-y-4">
        {[...Array(5)].map((_, i) => <ConversationSkeleton key={i} />)}
      </div>
    </div>
  )
}