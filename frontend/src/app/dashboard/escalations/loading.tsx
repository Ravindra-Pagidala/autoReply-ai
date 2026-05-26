export default function Loading() {
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-3">
      <div className="skeleton h-6 w-36 rounded mb-6" />
      {[...Array(4)].map((_, i) => (
        <div key={i} className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-5 flex gap-3">
          <div className="skeleton w-9 h-9 rounded-lg flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="skeleton h-4 w-48 rounded" />
            <div className="skeleton h-3 w-64 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}