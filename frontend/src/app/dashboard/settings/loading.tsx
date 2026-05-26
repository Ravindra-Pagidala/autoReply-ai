export default function Loading() {
  return (
    <div className="p-6 max-w-3xl mx-auto space-y-4">
      <div className="skeleton h-6 w-24 rounded mb-6" />
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