export default function Loading() {
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <div className="skeleton h-6 w-32 rounded mb-6" />
      <div className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5 space-y-4">
        <div className="skeleton h-4 w-40 rounded" />
        <div className="flex gap-2">
          {[...Array(4)].map((_, i) => <div key={i} className="skeleton h-9 w-24 rounded-lg" />)}
        </div>
        <div className="skeleton h-12 w-full rounded-lg" />
      </div>
    </div>
  )
}