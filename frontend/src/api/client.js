const API_BASE = 'http://localhost:8000/api'

async function fetchJSON(url, options) {
  const res = await fetch(url, options)
  const data = await res.json()
  if (!res.ok) {
    const err = new Error(data.error || data.errors || `Request failed with status ${res.status}`)
    err.response = { data, status: res.status }
    throw err
  }
  return { data, status: res.status }
}

export const api = {
  submitEvent: (data) => fetchJSON(`${API_BASE}/events`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  }),
  listOrders: () => fetchJSON(`${API_BASE}/orders`),
  getOrder: (id) => fetchJSON(`${API_BASE}/orders/${id}`),
  getHistory: (id) => fetchJSON(`${API_BASE}/orders/${id}/history`),
  getAudit: (id) => fetchJSON(`${API_BASE}/orders/${id}/audit`),
  replay: (id, upTo) => fetchJSON(`${API_BASE}/orders/${id}/replay${upTo ? `?up_to=${upTo}` : ''}`),
  getStats: () => fetchJSON(`${API_BASE}/stats`),
  getAnomalies: () => fetchJSON(`${API_BASE}/anomalies`),
  getLocations: () => fetchJSON(`${API_BASE}/locations`),
  getInventory: (locId) => fetchJSON(`${API_BASE}/inventory/${locId}`),
  health: () => fetchJSON(`${API_BASE}/health`),
}
