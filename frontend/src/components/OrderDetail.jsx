import { useState, useEffect } from 'react'
import { api } from '../api/client'

export default function OrderDetail({ orderId }) {
  const [order, setOrder] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!orderId) return
    fetchOrder()
  }, [orderId])

  const fetchOrder = async () => {
    try {
      const [orderRes, histRes] = await Promise.all([
        api.getOrder(orderId),
        api.getHistory(orderId),
      ])
      setOrder(orderRes.data)
      setHistory(histRes.data)
      setLoading(false)
    } catch {
      setLoading(false)
    }
  }

  if (!orderId) return <div className="p-8 text-gray-500">Select an order from the dashboard.</div>
  if (loading) return <div className="p-8 text-gray-500">Loading...</div>
  if (!order) return <div className="p-8 text-red-500">Order not found.</div>

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold mb-6">Order: {orderId}</h2>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <div className="text-xs text-gray-500 uppercase">Status</div>
            <div className="text-lg font-semibold capitalize mt-1">{order.status}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Version</div>
            <div className="text-lg font-semibold mt-1">v{order.version}</div>
          </div>
          <div>
            <div className="text-xs text-gray-500 uppercase">Source of Truth</div>
            <div className="text-lg font-semibold mt-1 capitalize">{order.source_of_truth}</div>
          </div>
        </div>

        <div className="mt-6">
          <div className="text-xs text-gray-500 uppercase mb-2">Items</div>
          {order.items?.length > 0 ? (
            <div className="space-y-1">
              {order.items.map((item, i) => (
                <div key={i} className="flex justify-between bg-gray-50 px-4 py-2 rounded">
                  <span>{item.name}</span>
                  <span className="font-medium">x{item.quantity}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-gray-400 text-sm">No items</div>
          )}
        </div>
      </div>

      <h3 className="text-lg font-bold mb-4">Version History</h3>
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-100 border-b">
            <tr>
              <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Version</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Items</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Event ID</th>
              <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200">
            {history.map(h => (
              <tr key={h.id}>
                <td className="px-6 py-4 text-sm">v{h.version}</td>
                <td className="px-6 py-4 text-sm capitalize">{h.status}</td>
                <td className="px-6 py-4 text-sm">{h.items?.length || 0} items</td>
                <td className="px-6 py-4 text-sm text-gray-500">{h.last_event_id}</td>
                <td className="px-6 py-4 text-sm text-gray-500">{new Date(h.created_at).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
