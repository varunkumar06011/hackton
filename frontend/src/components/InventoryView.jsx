import { useState, useEffect } from 'react'
import { api } from '../api/client'

export default function InventoryView() {
  const [locations, setLocations] = useState([])
  const [selectedLoc, setSelectedLoc] = useState(null)
  const [inventory, setInventory] = useState([])

  useEffect(() => {
    api.getLocations().then(res => {
      setLocations(res.data)
      if (res.data.length > 0) setSelectedLoc(res.data[0].id)
    }).catch(() => {})
  }, [])

  useEffect(() => {
    if (selectedLoc) {
      api.getInventory(selectedLoc).then(res => setInventory(res.data.items || [])).catch(() => {})
    }
  }, [selectedLoc])

  return (
    <div className="p-8">
      <h2 className="text-2xl font-bold mb-6">Inventory Management</h2>

      <div className="flex gap-4 mb-6">
        {locations.map(loc => (
          <button
            key={loc.id}
            onClick={() => setSelectedLoc(loc.id)}
            className={`px-4 py-2 rounded-lg text-sm ${
              selectedLoc === loc.id ? 'bg-restaurant-accent text-white' : 'bg-white shadow text-gray-700'
            }`}
          >
            {loc.name}
          </button>
        ))}
      </div>

      {inventory.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
          No inventory data. Create locations and menu items via Django admin.
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-100 border-b">
              <tr>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Item</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Stock</th>
                <th className="text-left px-6 py-3 text-xs font-semibold text-gray-600 uppercase">Stock Level</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {inventory.map(item => (
                <tr key={item.id}>
                  <td className="px-6 py-4 text-sm font-medium">{item.name}</td>
                  <td className="px-6 py-4 text-sm">{item.stock_quantity}</td>
                  <td className="px-6 py-4">
                    <div className="w-32 bg-gray-200 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${item.stock_quantity > 5 ? 'bg-green-500' : item.stock_quantity > 0 ? 'bg-orange-500' : 'bg-red-500'}`}
                        style={{ width: `${Math.min(item.stock_quantity * 10, 100)}%` }}
                      />
                    </div>
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
