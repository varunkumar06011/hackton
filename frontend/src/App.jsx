import { useState, useEffect } from 'react'
import { api } from './api/client'
import Dashboard from './components/Dashboard'
import OrderDetail from './components/OrderDetail'
import AuditTrail from './components/AuditTrail'
import ReplayTimeline from './components/ReplayTimeline'
import InventoryView from './components/InventoryView'
import AnomalyAlerts from './components/AnomalyAlerts'
import EventSubmitter from './components/EventSubmitter'

const TABS = [
  { id: 'dashboard', label: 'Dashboard', icon: '📋' },
  { id: 'submit', label: 'Submit Event', icon: '📤' },
  { id: 'detail', label: 'Order Detail', icon: '📄' },
  { id: 'audit', label: 'Audit Trail', icon: '🔍' },
  { id: 'replay', label: 'Replay', icon: '🔄' },
  { id: 'inventory', label: 'Inventory', icon: '📦' },
  { id: 'anomalies', label: 'Anomalies', icon: '⚠️' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState('dashboard')
  const [selectedOrder, setSelectedOrder] = useState(null)
  const [anomalyCount, setAnomalyCount] = useState(0)

  useEffect(() => {
    api.getAnomalies().then(r => setAnomalyCount(r.data.length)).catch(() => {})
  }, [activeTab])

  const selectOrder = (orderId) => {
    setSelectedOrder(orderId)
    setActiveTab('detail')
  }

  return (
    <div className="flex h-screen bg-gray-50">
      <div className="w-64 bg-restaurant-sidebar text-white flex flex-col">
        <div className="p-6 border-b border-gray-700">
          <div className="flex items-center gap-3">
            <span className="text-2xl">🍽️</span>
            <div>
              <h1 className="text-lg font-bold">VGrand</h1>
              <p className="text-xs text-gray-400">Order Resolution Engine</p>
            </div>
          </div>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {TABS.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition ${
                activeTab === tab.id
                  ? 'bg-restaurant-accent text-white'
                  : 'text-gray-400 hover:bg-gray-700 hover:text-white'
              }`}
            >
              <span className="text-base">{tab.icon}</span>
              <span>{tab.label}</span>
              {tab.id === 'anomalies' && anomalyCount > 0 && (
                <span className="ml-auto bg-restaurant-gold text-white text-xs px-2 py-0.5 rounded-full">
                  {anomalyCount}
                </span>
              )}
            </button>
          ))}
        </nav>
      </div>

      <div className="flex-1 overflow-auto">
        {activeTab === 'dashboard' && <Dashboard onSelectOrder={selectOrder} />}
        {activeTab === 'submit' && <EventSubmitter />}
        {activeTab === 'detail' && <OrderDetail orderId={selectedOrder} onBack={() => setActiveTab('dashboard')} />}
        {activeTab === 'audit' && <AuditTrail orderId={selectedOrder} />}
        {activeTab === 'replay' && <ReplayTimeline orderId={selectedOrder} />}
        {activeTab === 'inventory' && <InventoryView />}
        {activeTab === 'anomalies' && <AnomalyAlerts />}
      </div>
    </div>
  )
}
