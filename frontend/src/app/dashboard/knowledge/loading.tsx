export default function Loading() {
  return (
    <div className="p-6 max-w-4xl mx-auto space-y-4">
      <div className="skeleton h-6 w-40 rounded mb-6" />
      <div className="skeleton h-40 w-full rounded-xl mb-6" />
      {[...Array(3)].map((_, i) => (
        <div key={i} className="bg-[#16162A] border border-[#1E1E35] rounded-xl p-4 flex gap-3">
          <div className="skeleton w-9 h-9 rounded-lg flex-shrink-0" />
          <div className="flex-1 space-y-2">
            <div className="skeleton h-3 w-48 rounded" />
            <div className="skeleton h-2.5 w-32 rounded" />
          </div>
        </div>
      ))}
    </div>
  )
}