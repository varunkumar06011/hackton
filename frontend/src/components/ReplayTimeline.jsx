import { useState, useEffect } from 'react'
import { api } from '../api/client'

export default function ReplayTimeline({ orderId }) {
  const [replay, setReplay] = useState(null)
  const [loading, setLoading] = useState(true)
  const [upTo, setUpTo] = useState('')

  useEffect(() => {
    if (!orderId) return
    fetchReplay()
  }, [orderId, upTo])

  const fetchReplay = async () => {
    try {
      const res = await api.replay(orderId, upTo || null)
      setReplay(res.data)
      setLoading(false)
    } catch {
      setLoading(false)
    }
  }

  if (!orderId) return <div className="p-8 text-gray-500">Select an order from the dashboard.</div>
  if (loading) return <div className="p-8 text-gray-500">Loading...</div>
  if (!replay) return <div className="p-8 text-gray-500">No replay data found.</div>

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Replay: {orderId}</h2>
        <div className="flex items-center gap-2">
          <input
            type="text"
            placeholder="up_to (ISO 8601)"
            value={upTo}
            onChange={e => setUpTo(e.target.value)}
            className="border rounded px-3 py-1 text-sm w-64"
          />
          <button onClick={fetchReplay} className="bg-restaurant-accent text-white px-4 py-1 rounded text-sm">
            Replay
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="text-sm text-gray-500">Events Replayed: <span className="font-bold">{replay.events_replayed}</span></div>
        {replay.rejected_events?.length > 0 && (
          <div className="text-sm text-red-500 mt-1">Rejected: {replay.rejected_events.join(', ')}</div>
        )}
      </div>

      <div className="space-y-3">
        {replay.timeline?.map(step => (
          <div key={step.step} className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center gap-4 mb-3">
              <div className="w-8 h-8 bg-restaurant-accent text-white rounded-full flex items-center justify-center text-sm font-bold">
                {step.step}
              </div>
              <div className="flex-1">
                <div className="font-medium text-sm">{step.event_id}</div>
                <div className="text-xs text-gray-500">
                  {step.source} | {step.timestamp} | <span className="font-medium">{step.rule}</span>
                </div>
              </div>
            </div>
            <div className="ml-12 bg-gray-50 p-3 rounded text-xs">
              <div className="mb-1"><span className="text-gray-500">Status:</span> <span className="font-semibold">{step.state_after.status}</span></div>
              <div className="mb-1"><span className="text-gray-500">Items:</span> {step.state_after.items?.map(i => `${i.name} x${i.quantity}`).join(', ') || 'none'}</div>
              <div><span className="text-gray-500">Source:</span> {step.state_after.source_of_truth}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
