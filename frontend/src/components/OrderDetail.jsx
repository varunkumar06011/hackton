import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { statusBadge } from './badges'

// TODO(owner): wire onBack in App.jsx -> <OrderDetail orderId={selectedOrder} onBack={() => setActiveTab('dashboard')} />
export default function OrderDetail({ orderId, onBack }) {
  const [order, setOrder] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState(null)
  const [historyError, setHistoryError] = useState(null)

  useEffect(() => {
    if (!orderId) return
    fetchOrder()
  }, [orderId])

  const fetchOrder = async () => {
    // First load blanks the screen; refreshes keep existing data visible.
    const isFirstLoad = !order
    if (isFirstLoad) {
      setLoading(true)
      setError(null)
    } else {
      setRefreshing(true)
    }
    setHistoryError(null)

    try {
      // allSettled so a failed history fetch doesn't hide the order.
      const [orderRes, histRes] = await Promise.allSettled([
        api.getOrder(orderId),
        api.getHistory(orderId),
      ])

      if (orderRes.status === 'fulfilled') {
        setOrder(orderRes.value.data)
      } else {
        setError(orderRes.reason?.message || 'Failed to load order.')
        setOrder(null)
      }

      if (histRes.status === 'fulfilled') {
        setHistory(histRes.value.data)
      } else {
        setHistory([])
        setHistoryError(histRes.reason?.message || 'Failed to load version history.')
      }
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  if (!orderId) return <div className="p-8 text-gray-500">Select an order from the dashboard.</div>
  if (loading) return <div className="p-8 text-gray-500">Loading...</div>
  if (error) return (
    <div className="p-8">
      <div className="text-red-500 mb-4">{error}</div>
      {/* TODO(owner): style/position the back + retry buttons to match the app */}
      <div className="flex gap-2">
        {onBack && (
          <button onClick={onBack} className="px-3 py-1.5 bg-gray-200 rounded text-sm">Back</button>
        )}
        <button onClick={fetchOrder} className="px-3 py-1.5 bg-gray-200 rounded text-sm">Retry</button>
      </div>
    </div>
  )
  if (!order) return <div className="p-8 text-red-500">Order not found.</div>

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-bold">Order: {orderId}</h2>
        <div className="flex items-center gap-2">
          {refreshing && <span className="text-xs text-gray-400">Refreshing…</span>}
          {/* TODO(owner): style/position the back + refresh buttons to match the app */}
          {onBack && (
            <button onClick={onBack} className="px-3 py-1.5 bg-gray-200 rounded text-sm">Back</button>
          )}
          <button onClick={fetchOrder} disabled={refreshing} className="px-3 py-1.5 bg-gray-200 rounded text-sm disabled:opacity-50">Refresh</button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6 mb-6">
        <div className="grid grid-cols-3 gap-4">
          <div>
            <div className="text-xs text-gray-500 uppercase">Status</div>
            <div className="mt-1">{statusBadge(order.status)}</div>
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
          {Array.isArray(order.items) && order.items.length > 0 ? (
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
      {historyError ? (
        <div className="bg-white rounded-lg shadow p-6 text-red-500 text-sm">{historyError}</div>
      ) : history.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-6 text-center text-gray-500 text-sm">
          No version history recorded for this order.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden overflow-x-auto">
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
                  <td className="px-6 py-4 text-sm">{statusBadge(h.status)}</td>
                  <td className="px-6 py-4 text-sm">{h.items?.length || 0} items</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{h.last_event_id}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{new Date(h.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
