import { useState } from 'react'
import { api } from '../api/client'

const FIXTURES = {
  '01_duplicate_events': [
    {"event_id": "dup-1", "source": "pos", "order_id": "ORD-001", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 2}], "status": "pending"},
    {"event_id": "dup-1", "source": "pos", "order_id": "ORD-001", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 2}], "status": "pending"}
  ],
  '02_late_out_of_order': [
    {"event_id": "late-1", "source": "pos", "order_id": "ORD-002", "timestamp": "2026-08-15T10:05:00Z", "items": [{"name": "Pizza", "quantity": 1}], "status": "pending"},
    {"event_id": "late-2", "source": "mobile", "order_id": "ORD-002", "timestamp": "2026-08-15T10:10:00Z", "items": [], "status": "preparing"},
    {"event_id": "late-3", "source": "web", "order_id": "ORD-002", "timestamp": "2026-08-15T10:02:00Z", "items": [{"name": "Salad", "quantity": 1}], "status": "pending"}
  ],
  '03_conflicting_reservations': [
    {"event_id": "conf-1", "source": "pos", "order_id": "ORD-003", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Steak", "quantity": 2}], "status": "pending"},
    {"event_id": "conf-2", "source": "mobile", "order_id": "ORD-003", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Steak", "quantity": 1}], "status": "pending"}
  ],
  '04_conflicting_statuses': [
    {"event_id": "stat-1", "source": "pos", "order_id": "ORD-005", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Pasta", "quantity": 1}], "status": "pending"},
    {"event_id": "stat-2", "source": "pos", "order_id": "ORD-005", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"},
    {"event_id": "stat-3", "source": "web", "order_id": "ORD-005", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"}
  ],
  '05_partial_updates': [
    {"event_id": "part-1", "source": "web", "order_id": "ORD-006", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 2}, {"name": "Fries", "quantity": 1}], "status": "pending"},
    {"event_id": "part-2", "source": "pos", "order_id": "ORD-006", "timestamp": "2026-08-15T10:05:00Z", "items": [{"name": "Burger", "quantity": 3}], "status": "preparing"},
    {"event_id": "part-3", "source": "mobile", "order_id": "ORD-006", "timestamp": "2026-08-15T10:10:00Z", "items": [{"name": "Fries", "quantity": 0}], "status": "preparing"}
  ],
  '06_out_of_order_transitions': [
    {"event_id": "trans-1", "source": "pos", "order_id": "ORD-007", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Soup", "quantity": 1}], "status": "pending"},
    {"event_id": "trans-2", "source": "pos", "order_id": "ORD-007", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"},
    {"event_id": "trans-3", "source": "pos", "order_id": "ORD-007", "timestamp": "2026-08-15T10:10:00Z", "items": [], "status": "ready"},
    {"event_id": "trans-4", "source": "mobile", "order_id": "ORD-007", "timestamp": "2026-08-15T10:15:00Z", "items": [], "status": "preparing"}
  ],
  '07_anomaly_pattern': [
    {"event_id": "anom-1", "source": "web", "order_id": "ORD-008", "timestamp": "2026-08-15T10:10:00Z", "items": [{"name": "Tacos", "quantity": 2}], "status": "pending"},
    {"event_id": "anom-2", "source": "web", "order_id": "ORD-008", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "pending"},
    {"event_id": "anom-3", "source": "web", "order_id": "ORD-008", "timestamp": "2026-08-15T10:03:00Z", "items": [], "status": "pending"},
    {"event_id": "anom-4", "source": "web", "order_id": "ORD-008", "timestamp": "2026-08-15T10:01:00Z", "items": [], "status": "pending"}
  ],
}

export default function EventSubmitter() {
  const [formData, setFormData] = useState({
    event_id: '',
    source: 'pos',
    order_id: '',
    timestamp: '',
    items: [{ name: '', quantity: 1 }],
    status: 'pending',
  })
  const [response, setResponse] = useState(null)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const generateEventId = () => {
    setFormData(prev => ({ ...prev, event_id: `evt-${Date.now()}` }))
  }

  const addItem = () => {
    setFormData(prev => ({ ...prev, items: [...prev.items, { name: '', quantity: 1 }] }))
  }

  const removeItem = (idx) => {
    setFormData(prev => ({ ...prev, items: prev.items.filter((_, i) => i !== idx) }))
  }

  const updateItem = (idx, field, value) => {
    setFormData(prev => ({
      ...prev,
      items: prev.items.map((item, i) => i === idx ? { ...item, [field]: value } : item)
    }))
  }

  const submit = async () => {
    setSubmitting(true)
    setError(null)
    setResponse(null)
    try {
      const payload = {
        ...formData,
        items: formData.items.filter(i => i.name.trim() !== ''),
        timestamp: formData.timestamp || new Date().toISOString(),
      }
      const res = await api.submitEvent(payload)
      setResponse(res.data)
    } catch (err) {
      setError(err.message || 'Failed to submit event')
    }
    setSubmitting(false)
  }

  const loadFixture = (name) => {
    const events = FIXTURES[name]
    if (events && events.length > 0) {
      setFormData({ ...events[0], timestamp: events[0].timestamp })
    }
  }

  const submitAllFixtures = async (fixtureName) => {
    const events = FIXTURES[fixtureName]
    if (!events) return
    setSubmitting(true)
    const results = []
    for (const evt of events) {
      try {
        const res = await api.submitEvent(evt)
        results.push({ event_id: evt.event_id, status: res.data.status })
      } catch (err) {
        results.push({ event_id: evt.event_id, error: err.message })
      }
    }
    setResponse({ fixtureResults: results })
    setSubmitting(false)
  }

  return (
    <div className="p-8 max-w-2xl">
      <h2 className="text-2xl font-bold mb-6">Submit Order Event</h2>

      <div className="mb-6">
        <div className="text-xs text-gray-500 uppercase mb-2">Quick Load Fixture</div>
        <div className="flex flex-wrap gap-2">
          {Object.keys(FIXTURES).map(name => (
            <div key={name} className="flex items-center gap-1">
              <button
                onClick={() => loadFixture(name)}
                className="bg-gray-100 hover:bg-gray-200 px-3 py-1 rounded text-xs"
              >
                {name}
              </button>
              <button
                onClick={() => submitAllFixtures(name)}
                className="bg-restaurant-accent text-white px-2 py-1 rounded text-xs"
              >
                Submit All
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="text-xs text-gray-500 uppercase">Event ID</label>
            <div className="flex gap-2">
              <input
                type="text"
                value={formData.event_id}
                onChange={e => setFormData(prev => ({ ...prev, event_id: e.target.value }))}
                className="border rounded px-3 py-2 text-sm w-full mt-1"
                placeholder="evt-001"
              />
              <button onClick={generateEventId} className="bg-gray-100 px-2 rounded text-xs">Gen</button>
            </div>
          </div>
          <div>
            <label className="text-xs text-gray-500 uppercase">Source</label>
            <select
              value={formData.source}
              onChange={e => setFormData(prev => ({ ...prev, source: e.target.value }))}
              className="border rounded px-3 py-2 text-sm w-full mt-1"
            >
              <option value="pos">POS</option>
              <option value="mobile">Mobile</option>
              <option value="web">Web</option>
            </select>
          </div>
          <div>
            <label className="text-xs text-gray-500 uppercase">Order ID</label>
            <input
              type="text"
              value={formData.order_id}
              onChange={e => setFormData(prev => ({ ...prev, order_id: e.target.value }))}
              className="border rounded px-3 py-2 text-sm w-full mt-1"
              placeholder="ORD-001"
            />
          </div>
          <div>
            <label className="text-xs text-gray-500 uppercase">Timestamp</label>
            <input
              type="text"
              value={formData.timestamp}
              onChange={e => setFormData(prev => ({ ...prev, timestamp: e.target.value }))}
              className="border rounded px-3 py-2 text-sm w-full mt-1"
              placeholder="2026-08-15T10:00:00Z"
            />
          </div>
        </div>

        <div>
          <label className="text-xs text-gray-500 uppercase">Status</label>
          <select
            value={formData.status}
            onChange={e => setFormData(prev => ({ ...prev, status: e.target.value }))}
            className="border rounded px-3 py-2 text-sm w-full mt-1"
          >
            <option value="pending">⏳ Pending</option>
            <option value="preparing">🔥 Preparing</option>
            <option value="ready">✅ Ready</option>
            <option value="delivered">📦 Delivered</option>
            <option value="cancelled">❌ Cancelled</option>
          </select>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <label className="text-xs text-gray-500 uppercase">Items</label>
            <button onClick={addItem} className="text-xs text-restaurant-accent">
              + Add Item
            </button>
          </div>
          {formData.items.map((item, idx) => (
            <div key={idx} className="flex gap-2 mb-2">
              <input
                type="text"
                value={item.name}
                onChange={e => updateItem(idx, 'name', e.target.value)}
                className="border rounded px-3 py-1 text-sm flex-1"
                placeholder="Item name"
              />
              <input
                type="number"
                value={item.quantity}
                onChange={e => updateItem(idx, 'quantity', parseInt(e.target.value) || 0)}
                className="border rounded px-3 py-1 text-sm w-20"
                min="0"
              />
              <button onClick={() => removeItem(idx)} className="text-red-400 hover:text-red-600 text-sm px-2">
                ✕
              </button>
            </div>
          ))}
        </div>

        <button
          onClick={submit}
          disabled={submitting}
          className="bg-restaurant-accent text-white px-6 py-2 rounded-lg text-sm disabled:opacity-50"
        >
          {submitting ? 'Submitting...' : '📤 Submit Event'}
        </button>
      </div>

      {error && (
        <div className="mt-4 bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="text-sm font-semibold text-red-700">Error</div>
          <pre className="text-xs text-red-600 mt-1">{typeof error === 'string' ? error : JSON.stringify(error, null, 2)}</pre>
        </div>
      )}

      {response && (
        <div className="mt-4 bg-green-50 border border-green-200 rounded-lg p-4">
          <div className="text-sm font-semibold text-green-700">Response</div>
          <pre className="text-xs text-green-600 mt-1 overflow-auto">{JSON.stringify(response, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}
