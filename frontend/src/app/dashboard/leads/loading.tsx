import { TableRowSkeleton } from '@/components/ui/Skeleton'

export default function LeadsLoading() {
  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="skeleton h-6 w-24 rounded mb-6" />
      <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#1E1E35]">
              {[...Array(6)].map((_, i) => (
                <th key={i} className="px-4 py-3">
                  <div className="skeleton h-3 w-16 rounded" />
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-[#1E1E35]/50">
            {[...Array(8)].map((_, i) => <TableRowSkeleton key={i} cols={6} />)}
          </tbody>
        </table>
      </div>
    </div>
  )
}