import { useState, useEffect } from 'react'
import { api } from '../api/client'

export default function AuditTrail({ orderId }) {
  const [audits, setAudits] = useState([])
  const [loading, setLoading] = useState(true)
  const [expanded, setExpanded] = useState({})

  useEffect(() => {
    if (!orderId) return
    fetchAudits()
  }, [orderId])

  const fetchAudits = async () => {
    try {
      const res = await api.getAudit(orderId)
      setAudits(res.data)
      setLoading(false)
    } catch {
      setLoading(false)
    }
  }

  if (!orderId) return <div className="p-8 text-gray-500">Select an order from the dashboard.</div>
  if (loading) return <div className="p-8 text-gray-500">Loading...</div>
  if (audits.length === 0) return <div className="p-8 text-gray-500">No audit trail found for this order.</div>

  const toggle = (id) => setExpanded(prev => ({ ...prev, [id]: !prev[id] }))

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold mb-6">Audit Trail: {orderId}</h2>
      <div className="space-y-3">
        {audits.map(audit => (
          <div key={audit.id} className="bg-white rounded-lg shadow">
            <button
              onClick={() => toggle(audit.id)}
              className="w-full flex items-center gap-3 p-4 text-left"
            >
              <span className="text-sm">{expanded[audit.id] ? '▼' : '▶'}</span>
              <span className="font-medium text-sm">{audit.resolution_rule}</span>
              <span className="text-xs text-gray-400 ml-auto">
                {new Date(audit.decision_timestamp).toLocaleString()}
              </span>
            </button>
            {expanded[audit.id] && (
              <div className="px-4 pb-4 space-y-4">
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-1">Explanation</div>
                  <p className="text-sm text-gray-700">{audit.rule_explanation}</p>
                </div>
                <div>
                  <div className="text-xs text-gray-500 uppercase mb-1">Events Considered</div>
                  <div className="flex flex-wrap gap-2">
                    {audit.event_ids_considered?.map(eid => (
                      <span key={eid} className="bg-gray-100 px-2 py-1 rounded text-xs">{eid}</span>
                    ))}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <div className="text-xs text-gray-500 uppercase mb-1">Previous State</div>
                    <pre className="bg-gray-50 p-3 rounded text-xs overflow-auto">
                      {JSON.stringify(audit.previous_state, null, 2)}
                    </pre>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 uppercase mb-1">Final State</div>
                    <pre className="bg-gray-50 p-3 rounded text-xs overflow-auto">
                      {JSON.stringify(audit.final_state, null, 2)}
                    </pre>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
