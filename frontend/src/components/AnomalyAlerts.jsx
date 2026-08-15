import { useState, useEffect } from 'react'
import { api } from '../api/client'

export default function AnomalyAlerts() {
  const [anomalies, setAnomalies] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.getAnomalies().then(res => {
      setAnomalies(res.data)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  if (loading) return <div className="p-8 text-gray-500">Loading...</div>

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold mb-6">Anomaly Alerts</h2>

      {anomalies.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No anomalies detected. The system is operating normally.
        </div>
      ) : (
        <div className="space-y-3">
          {anomalies.map(a => (
            <div key={a.id} className="bg-white rounded-lg shadow p-4 border-l-4 border-restaurant-gold">
              <div className="flex items-start gap-3">
                <span className="text-xl flex-shrink-0 mt-0.5">⚠️</span>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-sm">{a.pattern_type}</span>
                    <span className="text-xs text-gray-400">from {a.source}</span>
                  </div>
                  <p className="text-sm text-gray-600 mt-1">{a.description}</p>
                  <div className="text-xs text-gray-400 mt-2">
                    {new Date(a.detected_at).toLocaleString()}
                    {a.order_id && <span className="ml-2">| Order: {a.order_id}</span>}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
