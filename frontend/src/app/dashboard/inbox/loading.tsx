export default function InboxLoading() {
  return (
    <div className="flex h-[calc(100vh-56px)]">
      <div className="w-80 border-r border-[#1E1E35] bg-[#16162A] p-4 space-y-3">
        <div className="skeleton h-5 w-16 rounded mb-4" />
        {[...Array(7)].map((_, i) => (
          <div key={i} className="flex gap-3 p-2">
            <div className="skeleton w-8 h-8 rounded-full flex-shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="skeleton h-3 w-28 rounded" />
              <div className="skeleton h-2.5 w-20 rounded" />
            </div>
          </div>
        ))}
      </div>
      <div className="flex-1 flex items-center justify-center bg-[#0F0F1A]">
        <div className="skeleton w-12 h-12 rounded-xl" />
      </div>
    </div>
  )
}