import { useState, useEffect } from 'react'
import { api } from '../api/client'

const STATUS_EMOJI = {
  pending: '⏳',
  preparing: '🔥',
  ready: '✅',
  delivered: '📦',
  cancelled: '❌',
}

const statusBadge = (status) => {
  const cls = {
    pending: 'badge-pending',
    preparing: 'badge-preparing',
    ready: 'badge-ready',
    delivered: 'badge-delivered',
    cancelled: 'badge-cancelled',
  }
  return <span className={cls[status] || 'badge-pending'}>{STATUS_EMOJI[status]} {status}</span>
}

export default function Dashboard({ onSelectOrder }) {
  const [orders, setOrders] = useState([])
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetchOrders()
    fetchStats()
  }, [])

  const fetchOrders = async () => {
    try {
      const res = await api.listOrders()
      setOrders(res.data)
      setLoading(false)
    } catch (err) {
      setError('Failed to load orders. Is the backend running?')
      setLoading(false)
    }
  }

  const fetchStats = async () => {
    try {
      const res = await api.getStats()
      setStats(res.data)
    } catch {
    }
  }

  if (loading) return <div className="p-8 text-gray-500">Loading orders...</div>
  if (error) return <div className="p-8 text-red-500">{error}</div>

  const statusCounts = orders.reduce((acc, o) => {
    acc[o.status] = (acc[o.status] || 0) + 1
    return acc
  }, {})

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold mb-6">Order Dashboard</h2>

      {stats && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-3xl font-bold text-gray-800">{stats.total_events}</div>
            <div className="text-sm text-gray-500 mt-1">Total Events</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-3xl font-bold text-gray-800">{stats.total_orders}</div>
            <div className="text-sm text-gray-500 mt-1">Total Orders</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-3xl font-bold text-gray-800">{stats.total_audit_entries}</div>
            <div className="text-sm text-gray-500 mt-1">Audit Entries</div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="text-3xl font-bold text-gray-800">{stats.rejected_events}</div>
            <div className="text-sm text-gray-500 mt-1">Rejected Events</div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-5 gap-4 mb-8">
        {['pending', 'preparing', 'ready', 'delivered', 'cancelled'].map(s => (
          <div key={s} className="bg-white rounded-lg shadow p-4">
            <div className="text-3xl font-bold text-gray-800">{statusCounts[s] || 0}</div>
            <div className="text-sm text-gray-500 mt-1 capitalize">{STATUS_EMOJI[s]} {s}</div>
          </div>
        ))}
      </div>

      {orders.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No orders yet. Submit events to see them here.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-100 border-b">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Order ID</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Status</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Items</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Version</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Source</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Last Event</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {orders.map(order => (
                <tr
                  key={order.id}
                  onClick={() => onSelectOrder(order.order_id)}
                  className="hover:bg-gray-50 cursor-pointer"
                >
                  <td className="px-6 py-4 text-sm font-medium text-gray-900">{order.order_id}</td>
                  <td className="px-6 py-4">{statusBadge(order.status)}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{order.items?.length || 0} items</td>
                  <td className="px-6 py-4 text-sm text-gray-500">v{order.version}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">{order.source_of_truth}</td>
                  <td className="px-6 py-4 text-sm text-gray-500">
                    {order.last_event_timestamp ? new Date(order.last_event_timestamp).toLocaleString() : '-'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
