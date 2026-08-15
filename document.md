# VGrand Restaurant — Order Conflict Resolution Engine

## Technical Design & Implementation Document

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Data Models](#3-data-models)
4. [Core Algorithms](#4-core-algorithms)
5. [API Reference](#5-api-reference)
6. [Conflict Resolution Rules](#6-conflict-resolution-rules)
7. [Audit Trail Design](#7-audit-trail-design)
8. [Replay Engine](#8-replay-engine)
9. [Inventory Management](#9-inventory-management)
10. [Anomaly Detection](#10-anomaly-detection)
11. [Driver Notification](#11-driver-notification)
12. [Frontend Dashboard](#12-frontend-dashboard)
13. [Fixture Data](#13-fixture-data)
14. [Management Commands](#14-management-commands)
15. [Test Suite](#15-test-suite)
16. [Non-Functional Requirements](#16-non-functional-requirements)
17. [Environment Configuration](#17-environment-configuration)
18. [Project Structure](#18-project-structure)

---

## 1. System Overview

VGrand Restaurant operates three order channels — POS terminals, mobile delivery app, and web reservations. Each channel independently submits order events (status changes, item additions/removals). The system must:

- **Ingest** events from all three channels into a single immutable log
- **Resolve** conflicts when multiple channels report different states for the same order at the same time
- **Maintain** a versioned, append-only order state that can be queried at any point in time
- **Audit** every resolution decision with a human-readable explanation
- **Replay** events to reconstruct historical state deterministically

### Design Principles

| Principle | Implementation |
|-----------|---------------|
| **Determinism** | Events sorted by `(timestamp, source_priority, event_id)` — same input always produces same output |
| **Idempotency** | Duplicate `event_id` values are detected and ignored — no side effects |
| **Replayability** | State is derived from immutable events via a pure reducer function — no hidden state |
| **Auditability** | Every resolution creates an `AuditLog` entry with rule, explanation, events considered, and state diff |
| **Immutability** | Events are never modified or deleted. `OrderState` is append-only (new version per resolution) |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
│  Dashboard │ Submit Event │ Order Detail │ Audit │ Replay │ ... │
└──────────────────────────┬──────────────────────────────────────┘
                           │ native fetch()
┌──────────────────────────▼──────────────────────────────────────┐
│                    Django REST API (:8000)                       │
│  POST /api/events  →  validate  →  dedup  →  save Event          │
│                                    →  reducer(sorted_events)      │
│                                    →  new OrderState version      │
│                                    →  AuditLog entry              │
│                                    →  notify_driver (if ready)    │
│                                    →  detect_anomalies            │
│                                    →  response (state + audit)    │
│                                                                  │
│  GET /api/orders     →  list_all_orders (latest version each)    │
│  GET /api/orders/:id →  get_current_state                        │
│  GET /api/orders/:id/history → all versions                      │
│  GET /api/orders/:id/audit → full audit trail                    │
│  GET /api/orders/:id/replay → reducer timeline                   │
│  GET /api/orders/:id/state?version=N → historical state          │
│  GET /api/stats → aggregate counts                               │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                     Database (SQLite/PostgreSQL)                 │
│  Event (immutable) │ OrderState (versioned) │ AuditLog │ ...    │
└─────────────────────────────────────────────────────────────────┘
```

### Request Flow (POST /api/events)

```
1. validate_event(data)          → validates required fields, source, status, items
2. check_duplicate(event_id)     → returns existing event if already processed
3. save_event(data)              → creates immutable Event record (IntegrityError-safe)
4. resolve_event(event)          → the core:
   a. Fetch all events for order_id
   b. Sort by canonical key: (timestamp, source_priority, event_id)
   c. Run reducer() → final state + timeline + rejected events
   d. Create new OrderState version (append-only)
   e. Create AuditLog entry with explanation
   f. If location_id present: check + reserve inventory
5. notify_driver(order_id, status) → sends notification if status is "ready" or "delivered"
6. detect_anomalies(order_id, source) → checks for repeated late events, status oscillation
7. Response: { status, processing_time_ms, order_state, audit }
```

---

## 3. Data Models

### Event (Immutable Log)

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | CharField(100), unique, indexed | Client-generated unique identifier |
| `order_id` | CharField(100), indexed | Order this event belongs to |
| `source` | CharField(20) | One of: `pos`, `mobile`, `web` |
| `timestamp` | DateTimeField | Client-reported event time (ISO 8601) |
| `items` | JSONField (list) | Item changes: `[{"name": "Burger", "quantity": 2}]` |
| `status` | CharField(20) | One of: `pending`, `preparing`, `ready`, `delivered`, `cancelled` |
| `location_id` | CharField(100), nullable | Location for inventory reservation |
| `raw_payload` | JSONField (dict) | Original submitted payload (for debugging) |
| `received_at` | DateTimeField (auto) | Server receipt timestamp |
| `processed` | BooleanField | Whether the event has been through resolution |

**Meta**: `ordering = ["timestamp"]` — default sort by event timestamp ascending.

### OrderState (Versioned Projection)

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | CharField(100), indexed | Order identifier |
| `version` | IntegerField | Monotonically increasing per order (starts at 0) |
| `status` | CharField(20) | Current resolved status |
| `items` | JSONField (list) | Current merged item list |
| `last_event_id` | CharField(100) | Event that produced this state |
| `last_event_timestamp` | DateTimeField | Timestamp of last event |
| `source_of_truth` | CharField(20) | Source of the last applied event |
| `created_at` | DateTimeField (auto) | When this version was created |

**Meta**: `ordering = ["-version"]`, `unique_together = ["order_id", "version"]`.

### AuditLog (Decision Trace)

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | CharField(100), indexed | Order identifier |
| `event_ids_considered` | JSONField (list) | All event IDs sorted in canonical order |
| `events_detail` | JSONField (list) | Full event objects considered |
| `resolution_rule` | CharField(100) | Rule applied (see §6) |
| `rule_explanation` | TextField | Human-readable explanation |
| `previous_state` | JSONField (dict) | State before this resolution |
| `final_state` | JSONField (dict) | State after this resolution |
| `decision_timestamp` | DateTimeField (auto) | When the decision was made |

### Location

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField(100) | Location name (e.g., "Downtown") |
| `address` | CharField(200) | Physical address |
| `created_at` | DateTimeField (auto) | Creation timestamp |

### MenuItem

| Field | Type | Description |
|-------|------|-------------|
| `name` | CharField(100) | Item name |
| `location` | ForeignKey → Location | Location this item belongs to |
| `stock_quantity` | IntegerField | Current stock level |

### InventoryReservation

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | CharField(100), indexed | Order holding the reservation |
| `item` | ForeignKey → MenuItem | Reserved menu item |
| `quantity` | IntegerField | Reserved quantity |
| `status` | CharField(20) | `reserved` or `released` |
| `created_at` | DateTimeField (auto) | Reservation timestamp |

### AnomalyAlert

| Field | Type | Description |
|-------|------|-------------|
| `source` | CharField(20) | Channel that triggered the anomaly |
| `pattern_type` | CharField(50) | `repeated_late` or `status_oscillation` |
| `description` | TextField | Human-readable description |
| `order_id` | CharField(100), nullable | Related order (if applicable) |
| `detected_at` | DateTimeField (auto) | Detection timestamp |
| `resolved` | BooleanField | Whether the alert has been addressed |

### DriverNotification

| Field | Type | Description |
|-------|------|-------------|
| `order_id` | CharField(100), indexed | Related order |
| `driver_id` | CharField(50) | Driver identifier (default: `DRV-001`) |
| `message` | TextField | Notification message |
| `status` | CharField(20) | `sent` |
| `created_at` | DateTimeField (auto) | Send timestamp |

---

## 4. Core Algorithms

### 4.1 Canonical Sort Key

```python
def canonical_sort_key(event):
    return (event.timestamp, SOURCE_PRIORITY.get(event.source, 99), event.event_id)
```

**Source priority** (defined in `settings.py`):

| Source | Priority |
|--------|----------|
| `pos` | 0 (highest) |
| `mobile` | 1 |
| `web` | 2 (lowest) |

Events are sorted by `(timestamp, source_priority, event_id)`. This ensures:
- Earlier timestamps process first
- Same-timestamp events resolve by source priority (POS wins)
- `event_id` is the final tiebreaker for full determinism

### 4.2 Reducer Function

The reducer is a **pure function** — same input always produces same output. It takes a list of events and returns `(final_state, timeline, rejected_events)`.

```python
def reducer(events, up_to=None):
    # 1. Filter by up_to timestamp (for replay)
    # 2. Sort events by canonical key
    # 3. Initialize empty state
    # 4. For each event in sorted order:
    #    a. Determine rule:
    #       - initial_event (first event, no prior status)
    #       - no_status_change (same status as current)
    #       - valid_transition (allowed by VALID_TRANSITIONS)
    #       - invalid_transition_rejected (not allowed)
    #    b. Update state (status, items, last_event, source)
    #       — skipped for invalid_transition_rejected (items NOT merged)
    #    c. Record timeline snapshot
    # 5. Return final state, timeline, rejected events
```

**Item merge logic**:

```python
def merge_items(current_items, new_items):
    # Build dict: {name: quantity}
    # For each new item:
    #   quantity > 0 → set/overwrite
    #   quantity = 0 → remove item
    # Return as list of {name, quantity}
```

### 4.3 Valid Status Transitions

Defined in `settings.py`:

```
pending → preparing, cancelled
preparing → ready, cancelled
ready → delivered, cancelled
delivered → (terminal, no transitions)
cancelled → (terminal, no transitions)
```

Any status → `cancelled` is always valid (except from terminal states).

### 4.4 Event Validation

Performed by `validate_event()` in `ingestion.py`:

| Check | Error if failed |
|-------|----------------|
| Required fields: `event_id`, `source`, `order_id`, `timestamp`, `status` | `Missing required field: {field}` |
| `source` in `["pos", "mobile", "web"]` | `Invalid source` |
| `status` in `["pending", "preparing", "ready", "delivered", "cancelled"]` | `Invalid status` |
| `items` is a list (if present) | `items must be a list` |
| Each item has `name` (non-empty string) | `items[i].name is required` |
| Each item has `quantity` (non-negative integer) | `items[i].quantity must be a non-negative integer` |
| `timestamp` is valid ISO 8601 | `timestamp must be a valid ISO 8601 datetime string` |

### 4.5 Resolution Flow (`resolve_event`)

```
1. Fetch all events for the order from the Event table
2. Run reducer() on all events → final_state, timeline, rejected
3. Find the timeline step matching the newly submitted event's event_id
   → this gives us the correct rule for this event
4. Create new OrderState version (prev_version + 1)
5. Create AuditLog entry:
   - event_ids_considered: all event IDs in canonical order
   - events_detail: full event objects in canonical order
   - resolution_rule: the rule applied to this event
   - rule_explanation: human-readable explanation
   - previous_state: state before this resolution
   - final_state: state after this resolution
6. If event has location_id and items:
   → check_inventory() → if available, reserve_inventory()
   → if shortage, append to audit explanation
7. Mark event as processed
8. Return (order_state, audit)
```

---

## 5. API Reference

### POST /api/events

Submit a new order event.

**Request body**:
```json
{
  "event_id": "evt-001",
  "source": "pos",
  "order_id": "ORD-001",
  "timestamp": "2026-08-15T10:00:00Z",
  "items": [{"name": "Burger", "quantity": 2}],
  "status": "pending",
  "location_id": "1"
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `event_id` | Yes | Unique event identifier |
| `source` | Yes | `pos`, `mobile`, or `web` |
| `order_id` | Yes | Order identifier |
| `timestamp` | Yes | ISO 8601 timestamp |
| `status` | Yes | `pending`, `preparing`, `ready`, `delivered`, `cancelled` |
| `items` | No | List of `{"name": string, "quantity": non-negative int}`. Empty = no item change. |
| `location_id` | No | Location ID for inventory reservation |

**Response (201 — processed)**:
```json
{
  "status": "processed",
  "processing_time_ms": 18.55,
  "order_state": {
    "id": 1,
    "order_id": "ORD-001",
    "version": 0,
    "status": "pending",
    "items": [{"name": "Burger", "quantity": 2}],
    "last_event_id": "evt-001",
    "last_event_timestamp": "2026-08-15T10:00:00Z",
    "source_of_truth": "pos",
    "created_at": "2026-08-15T06:14:07Z"
  },
  "audit": {
    "resolution_rule": "initial_event",
    "explanation": "First event for order ORD-001. Status set to 'pending' from source 'pos'.",
    "event_ids_considered": ["evt-001"]
  }
}
```

**Response (200 — duplicate ignored)**:
```json
{
  "status": "duplicate_ignored",
  "event_id": "evt-001",
  "existing_state": { ... }
}
```

**Response (400 — validation error)**:
```json
{
  "status": "rejected",
  "errors": ["Invalid source. Must be one of: ['pos', 'mobile', 'web']"]
}
```

### GET /api/orders

List all orders with their latest state.

**Response (200)**:
```json
[
  {
    "id": 1,
    "order_id": "ORD-001",
    "version": 0,
    "status": "pending",
    "items": [{"name": "Burger", "quantity": 2}],
    "last_event_id": "evt-001",
    "last_event_timestamp": "2026-08-15T10:00:00Z",
    "source_of_truth": "pos",
    "created_at": "2026-08-15T06:14:07Z"
  }
]
```

### GET /api/orders/{order_id}

Get current state of a specific order.

**Response (200)**: Same as individual order object above.

**Response (404)**: `{"error": "Order not found"}`

### GET /api/orders/{order_id}/history

Get all versioned states for an order, ordered by version ascending.

**Response (200)**:
```json
[
  {"version": 0, "status": "pending", "items": [...], ...},
  {"version": 1, "status": "preparing", "items": [...], ...}
]
```

### GET /api/orders/{order_id}/audit

Get full audit trail for an order, ordered by decision timestamp ascending.

**Response (200)**:
```json
[
  {
    "id": 1,
    "order_id": "ORD-001",
    "event_ids_considered": ["evt-001"],
    "events_detail": [
      {
        "event_id": "evt-001",
        "source": "pos",
        "timestamp": "2026-08-15T10:00:00+00:00",
        "status": "pending",
        "items": [{"name": "Burger", "quantity": 2}]
      }
    ],
    "resolution_rule": "initial_event",
    "rule_explanation": "First event for order ORD-001. Status set to 'pending' from source 'pos'.",
    "previous_state": {},
    "final_state": {"status": "pending", "items": [...], "version": 0},
    "decision_timestamp": "2026-08-15T06:14:07Z"
  }
]
```

### GET /api/orders/{order_id}/replay

Replay all events for an order through the reducer to show the full timeline.

**Query params**:
- `up_to` (optional): ISO 8601 timestamp — only replay events up to this point

**Response (200)**:
```json
{
  "order_id": "ORD-002",
  "events_replayed": 3,
  "timeline": [
    {
      "step": 1,
      "event_id": "late-3",
      "source": "web",
      "timestamp": "2026-08-15T10:02:00+00:00",
      "rule": "initial_event",
      "state_after": {
        "status": "pending",
        "items": [{"name": "Salad", "quantity": 1}],
        "last_event_id": "late-3",
        "last_event_timestamp": "2026-08-15T10:02:00+00:00",
        "source_of_truth": "web"
      }
    }
  ],
  "final_state": { ... },
  "rejected_events": []
}
```

### GET /api/orders/{order_id}/state

Get historical state at a specific version or timestamp.

**Query params** (one required):
- `version`: Integer version number
- `timestamp`: ISO 8601 timestamp (returns latest state at or before this time)

**Response (200)**: OrderState object.

**Response (400)**: `{"error": "Provide 'version' or 'timestamp' query param"}`

### GET /api/stats

Get system-wide statistics.

**Response (200)**:
```json
{
  "total_events": 12,
  "total_orders": 5,
  "total_state_versions": 12,
  "total_audit_entries": 12,
  "rejected_events": 1,
  "duplicate_events": 2,
  "timestamp": "2026-08-15T06:18:17Z"
}
```

### GET /api/locations

List all restaurant locations.

### GET /api/inventory/{location_id}

Get inventory (menu items with stock) for a location.

### GET /api/anomalies

List all anomaly alerts.

### POST /api/notify/driver

Trigger a driver notification.

**Request body**: `{"order_id": "ORD-001", "status": "ready"}`

Notifications are only sent for `ready` or `delivered` statuses.

### GET /api/health

Health check endpoint.

**Response**: `{"status": "healthy", "timestamp": "2026-08-15T06:15:58Z"}`

---

## 6. Conflict Resolution Rules

### Resolution Rules

| Rule | When Applied | Effect |
|------|-------------|--------|
| `initial_event` | First event for an order (no prior status) | Sets status and items |
| `no_status_change` | Event has same status as current state | Items merged, status unchanged |
| `valid_transition` | Status change allowed by `VALID_TRANSITIONS` | Status updated, items merged |
| `invalid_transition_rejected` | Status change not allowed | Status unchanged, event logged as rejected, items NOT merged |
| `duplicate_ignored` | Event with same `event_id` already exists | No state change, existing state returned |

### Conflict Scenarios

**Same timestamp, different sources, different statuses**:
- Events sorted by source priority: `pos` (0) > `mobile` (1) > `web` (2)
- POS event processed first — its status becomes the current state
- Second event evaluated against the new current state
- If second event's status is a valid transition from the first → applied
- If invalid → rejected with explanation

**Same timestamp, different sources, different items**:
- Both events' items are merged (union by name, latest quantity wins)
- Source priority determines which event's status takes effect

**Late event (earlier timestamp arrives after newer events)**:
- Event is inserted into the Event table
- All events for the order are re-sorted by canonical key
- Reducer replays from scratch — late event naturally falls into correct position
- New OrderState version is created with the corrected state

**Partial item update**:
- Items with `quantity > 0`: adds or overwrites the item
- Items with `quantity = 0`: removes the item from the order
- Items not mentioned in the event: unchanged

### Source Priority Configuration

Defined in `backend/vgrand/settings.py`:

```python
SOURCE_PRIORITY = {'pos': 0, 'mobile': 1, 'web': 2}

VALID_TRANSITIONS = {
    'pending': ['preparing', 'cancelled'],
    'preparing': ['ready', 'cancelled'],
    'ready': ['delivered', 'cancelled'],
    'delivered': [],
    'cancelled': [],
}
```

---

## 7. Audit Trail Design

Every call to `resolve_event()` creates an `AuditLog` entry containing:

1. **`event_ids_considered`**: All event IDs for this order, sorted in canonical order
2. **`events_detail`**: Full event objects (event_id, source, timestamp, status, items) in canonical order
3. **`resolution_rule`**: The rule applied to the newly submitted event
4. **`rule_explanation`**: Human-readable explanation generated by `generate_explanation()`
5. **`previous_state`**: State before this resolution (status, items, version)
6. **`final_state`**: State after this resolution (status, items, version)

### Explanation Generation

The `generate_explanation()` function produces context-aware messages:

**Standard explanations** (no same-timestamp conflict):
- `initial_event`: "First event for order {order_id}. Status set to '{status}' from source '{source}'."
- `no_status_change`: "Event {event_id} from '{source}' confirmed status '{status}'. Items merged."
- `valid_transition`: "Event {event_id} from '{source}' transitioned status to '{status}'. Valid transition."
- `invalid_transition_rejected`: "Event {event_id} from '{source}' proposed invalid status transition to '{status}'. Rejected. Status remains '{current_status}'."

**Same-timestamp conflict explanations** (when two events share a timestamp):
- Detects same-timestamp events in the timeline
- Explains which source won the priority tiebreak
- Differentiates between: invalid transition after priority, no-status-change confirmation, or priority-based override

---

## 8. Replay Engine

The replay engine (`replay_engine.py`) reuses the same `reducer()` function used for live processing:

```python
def replay_order(order_id, up_to=None):
    events = list(Event.objects.filter(order_id=order_id))
    # Parse up_to timestamp if provided
    final_state, timeline, rejected = reducer(events, up_to=up_to_dt)
    return {
        "order_id": order_id,
        "events_replayed": len(timeline),
        "timeline": timeline,
        "final_state": final_state,
        "rejected_events": rejected,
    }
```

**Key properties**:
- **Deterministic**: Same events always produce the same timeline
- **Matches live state**: Replay output's `final_state` equals the latest `OrderState`
- **Supports `up_to` filter**: Can replay to any point in time
- **Shows rejected events**: Invalid transitions are visible in the timeline

---

## 9. Inventory Management

Inventory is managed per-location through `MenuItem` and `InventoryReservation` models.

### Check Inventory

`check_inventory(location_id, items)` verifies that all items have sufficient stock:

```python
def check_inventory(location_id, items):
    # For each item, find MenuItem by name + location_id
    # If stock_quantity < requested quantity → shortage
    # Returns {"available": bool, "shortages": [...]}
```

### Reserve Inventory

`reserve_inventory(order_id, items, location_id)` deducts stock and creates reservations:

```python
def reserve_inventory(order_id, items, location_id):
    # For each item:
    #   Find MenuItem, check stock, deduct quantity, save
    #   Create InventoryReservation record
```

### Release Inventory

`release_inventory(order_id)` restores stock for cancelled orders:

```python
def release_inventory(order_id):
    # Find all "reserved" InventoryReservations for order
    # Add quantity back to MenuItem.stock_quantity
    # Mark reservation as "released"
```

### Integration with Event Resolution

Inventory check/reservation is triggered in `resolve_event()` when `event.location_id` is present and the order has items. If inventory is insufficient, the shortage is appended to the audit explanation.

---

## 10. Anomaly Detection

The `detect_anomalies()` function in `anomaly_detector.py` checks for two patterns:

### Repeated Late Events

- Looks at events from the same source for the same order in the last 10 minutes
- An event is "late" if `event.timestamp < event.received_at - 1 minute`
- If more than 3 late events from the same source → `AnomalyAlert(pattern_type="repeated_late")`

### Status Oscillation

- Examines the full event history for an order
- Counts "oscillations" — where status changes direction (A→B→A pattern)
- If more than 3 oscillations → `AnomalyAlert(pattern_type="status_oscillation")`

---

## 11. Driver Notification

The `notify_driver()` function in `driver_notifier.py` creates a `DriverNotification` record when an order reaches `ready` or `delivered` status:

```python
def notify_driver(order_id, status):
    if status not in ["ready", "delivered"]:
        return None
    message = f"Order {order_id} is now {status}. Please proceed."
    # Create DriverNotification record
```

This is a dummy implementation — no actual push notification is sent. The notification is stored in the database and can be queried.

---

## 12. Frontend Dashboard

### Tech Stack (Constraint-Compliant)

| Requirement | Implementation |
|-------------|---------------|
| React.js | React 18 via Vite |
| Tailwind CSS | Tailwind CSS 3.4 |
| Native fetch | `src/api/client.js` — uses `fetch()` with error throwing on non-2xx |
| CSS/SVG timeline | CSS-based timeline in `ReplayTimeline.jsx` |
| No external icon libraries | Emoji characters (📋 📤 📄 🔍 🔄 📦 ⚠️ ⏳ 🔥 ✅ ❌) |

### Components

| Component | File | Description |
|-----------|------|-------------|
| **App** | `src/App.jsx` | Sidebar navigation with 7 tabs |
| **Dashboard** | `src/components/Dashboard.jsx` | Stats overview + order table with status badges |
| **EventSubmitter** | `src/components/EventSubmitter.jsx` | Form with fixture quick-load + submit-all buttons |
| **OrderDetail** | `src/components/OrderDetail.jsx` | Current state + version history table |
| **AuditTrail** | `src/components/AuditTrail.jsx` | Expandable audit entries with state diffs |
| **ReplayTimeline** | `src/components/ReplayTimeline.jsx` | Step-by-step replay with `up_to` filter |
| **InventoryView** | `src/components/InventoryView.jsx` | Per-location inventory with stock level bars |
| **AnomalyAlerts** | `src/components/AnomalyAlerts.jsx` | Alert panel with pattern type and description |

### API Client

`src/api/client.js` wraps `fetch()` with automatic JSON parsing and error throwing:

```javascript
const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'

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
```

`VITE_API_BASE` allows the deployed frontend (e.g. Vercel) to point at the deployed backend (e.g. Railway).

### Embedded Fixtures

The `EventSubmitter` component has all 7 fixtures embedded for quick testing via "Submit All" buttons.

---

## 13. Fixture Data

Seven fixture files in `backend/fixtures/` cover the interacting edge cases:

### Fixture 01: Duplicate Events

**File**: `01_duplicate_events.json`
**Tests**: Idempotency — same `event_id` submitted twice. Second submission is ignored.

```json
[
  {"event_id": "dup-1", "source": "pos", "order_id": "ORD-001", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 2}], "status": "pending"},
  {"event_id": "dup-1", "source": "pos", "order_id": "ORD-001", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 2}], "status": "pending"}
]
```

### Fixture 02: Late / Out-of-Order

**File**: `02_late_out_of_order.json`
**Tests**: Event with earlier timestamp arrives after newer events. Reducer sorts and recomputes.

```json
[
  {"event_id": "late-1", "source": "pos", "order_id": "ORD-002", "timestamp": "2026-08-15T10:05:00Z", "items": [{"name": "Pizza", "quantity": 1}], "status": "pending"},
  {"event_id": "late-2", "source": "mobile", "order_id": "ORD-002", "timestamp": "2026-08-15T10:10:00Z", "items": [], "status": "preparing"},
  {"event_id": "late-3", "source": "web", "order_id": "ORD-002", "timestamp": "2026-08-15T10:02:00Z", "items": [{"name": "Salad", "quantity": 1}], "status": "pending"}
]
```

### Fixture 03: Conflicting Reservations

**File**: `03_conflicting_reservations.json`
**Tests**: Same order, same timestamp, different sources, different quantities. Priority tiebreak resolves.

```json
[
  {"event_id": "conf-1", "source": "pos", "order_id": "ORD-003", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Steak", "quantity": 2}], "status": "pending"},
  {"event_id": "conf-2", "source": "mobile", "order_id": "ORD-003", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Steak", "quantity": 1}], "status": "pending"}
]
```

### Fixture 04: Conflicting Statuses

**File**: `04_conflicting_statuses.json`
**Tests**: Two valid status updates at the same timestamp. POS priority determines processing order.

```json
[
  {"event_id": "stat-1", "source": "pos", "order_id": "ORD-005", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Pasta", "quantity": 1}], "status": "pending"},
  {"event_id": "stat-2", "source": "pos", "order_id": "ORD-005", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"},
  {"event_id": "stat-3", "source": "web", "order_id": "ORD-005", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"}
]
```

### Fixture 05: Partial Updates

**File**: `05_partial_updates.json`
**Tests**: Item add, quantity change, item removal (quantity=0).

```json
[
  {"event_id": "part-1", "source": "web", "order_id": "ORD-006", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 2}, {"name": "Fries", "quantity": 1}], "status": "pending"},
  {"event_id": "part-2", "source": "pos", "order_id": "ORD-006", "timestamp": "2026-08-15T10:05:00Z", "items": [{"name": "Burger", "quantity": 3}], "status": "preparing"},
  {"event_id": "part-3", "source": "mobile", "order_id": "ORD-006", "timestamp": "2026-08-15T10:10:00Z", "items": [{"name": "Fries", "quantity": 0}], "status": "preparing"}
]
```

### Fixture 06: Out-of-Order Transitions

**File**: `06_out_of_order_transitions.json`
**Tests**: Invalid backward status transition (ready → preparing) is rejected.

```json
[
  {"event_id": "trans-1", "source": "pos", "order_id": "ORD-007", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Soup", "quantity": 1}], "status": "pending"},
  {"event_id": "trans-2", "source": "pos", "order_id": "ORD-007", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "preparing"},
  {"event_id": "trans-3", "source": "pos", "order_id": "ORD-007", "timestamp": "2026-08-15T10:10:00Z", "items": [], "status": "ready"},
  {"event_id": "trans-4", "source": "mobile", "order_id": "ORD-007", "timestamp": "2026-08-15T10:15:00Z", "items": [], "status": "preparing"}
]
```

### Fixture 07: Anomaly Pattern

**File**: `07_anomaly_pattern.json`
**Tests**: Repeated late events from the same source triggers anomaly detection.

```json
[
  {"event_id": "anom-1", "source": "web", "order_id": "ORD-008", "timestamp": "2026-08-15T10:10:00Z", "items": [{"name": "Tacos", "quantity": 2}], "status": "pending"},
  {"event_id": "anom-2", "source": "web", "order_id": "ORD-008", "timestamp": "2026-08-15T10:05:00Z", "items": [], "status": "pending"},
  {"event_id": "anom-3", "source": "web", "order_id": "ORD-008", "timestamp": "2026-08-15T10:03:00Z", "items": [], "status": "pending"},
  {"event_id": "anom-4", "source": "web", "order_id": "ORD-008", "timestamp": "2026-08-15T10:01:00Z", "items": [], "status": "pending"}
]
```

---

## 14. Management Commands

### load_fixture

Loads fixture JSON files through the full event ingestion pipeline (validate → dedup → save → resolve).

**Usage**:
```bash
python manage.py load_fixture <fixture_path> [--seed-inventory]
```

**Arguments**:
- `fixture_path`: Path to fixture JSON file (relative to `backend/` or absolute)
- `--seed-inventory`: Creates a default Location ("Downtown") with 9 MenuItems before loading

**Output**:
```
Seeded inventory: Location 'Downtown' with 9 menu items
  PROCESSED dup-1 -> order ORD-001 status=pending rule=initial_event
  DUPLICATE skipped: dup-1

Summary: 1 processed, 1 duplicates, 0 rejected, 0 errors
```

**Seeded Inventory** (with `--seed-inventory`):

| Item | Stock |
|------|-------|
| Burger | 10 |
| Pizza | 8 |
| Steak | 5 |
| Pasta | 6 |
| Fries | 15 |
| Salad | 12 |
| Soup | 7 |
| Tacos | 9 |
| Rice | 10 |

---

## 15. Test Suite

30 tests in `backend/orders/tests.py`, organized into 8 test classes:

### DuplicateEventTest (3 tests)

| Test | Description |
|------|-------------|
| `test_duplicate_event_ignored` | Submitting same event_id twice returns `duplicate_ignored` |
| `test_duplicate_does_not_create_new_event` | No new Event row created for duplicate |
| `test_duplicate_idempotent` | State unchanged after duplicate submission |

### LateEventTest (2 tests)

| Test | Description |
|------|-------------|
| `test_late_event_recomputes_state` | Late event with earlier timestamp correctly reorders |
| `test_late_event_items_merged_correctly` | Items from late event merge into correct position |

### ConflictResolutionTest (5 tests)

| Test | Description |
|------|-------------|
| `test_conflicting_status_same_timestamp_pos_wins` | POS priority over mobile at same timestamp |
| `test_conflicting_status_different_timestamp_latest_wins` | Later timestamp wins |
| `test_invalid_transition_rejected` | Backward transition (delivered→preparing) rejected |
| `test_conflicting_reservation_within_order` | Same order, same timestamp, different quantities |
| `test_audit_explanation_accuracy` | Audit explanation correctly describes the resolution |

### ReplayTest (3 tests)

| Test | Description |
|------|-------------|
| `test_replay_matches_live_state` | Replay final_state equals current OrderState |
| `test_replay_determinism` | Two replays produce identical results |
| `test_replay_with_up_to` | Replay with timestamp filter returns correct partial state |

### AuditTrailTest (4 tests)

| Test | Description |
|------|-------------|
| `test_audit_contains_all_events` | All event IDs present in audit |
| `test_audit_has_resolution_rule` | Resolution rule is set |
| `test_audit_has_previous_and_final_state` | Both state snapshots present |
| `test_audit_explanation_readable` | Explanation is a non-empty string |

### InventoryTest (2 tests)

| Test | Description |
|------|-------------|
| `test_inventory_check` | Insufficient stock is detected |
| `test_reservation_release` | Released inventory restores stock |

### ValidationTest (5 tests)

| Test | Description |
|------|-------------|
| `test_missing_required_field` | Missing field returns 400 |
| `test_invalid_source` | Invalid source returns 400 |
| `test_invalid_status` | Invalid status returns 400 |
| `test_valid_event_accepted` | Valid event returns 201 |
| `test_quantity_zero_allowed` | Quantity 0 is valid (item removal) |
| `test_negative_quantity_rejected` | Negative quantity returns 400 |

### EdgeCaseTest (3 tests)

| Test | Description |
|------|-------------|
| `test_get_nonexistent_order_404` | Nonexistent order returns 404 |
| `test_processing_time_in_response` | `processing_time_ms` present in response |
| `test_partial_update_item_removal` | Quantity 0 removes item from state |

### StatsEndpointTest (1 test)

| Test | Description |
|------|-------------|
| `test_stats_endpoint` | Stats endpoint returns counts |

### IntegrityErrorTest (1 test)

| Test | Description |
|------|-------------|
| `test_duplicate_integrity_error_handled` | IntegrityError from race condition returns `duplicate_ignored` |

### Running Tests

```bash
cd backend
python manage.py test --verbosity=2
```

---

## 16. Non-Functional Requirements

### Determinism

- Events sorted by `(timestamp, source_priority, event_id)` — no ambiguity
- Reducer is a pure function — no side effects, no hidden state
- Same events always produce the same state and timeline

### Idempotency

- `event_id` has a `unique` constraint at the database level
- Duplicate submissions return `duplicate_ignored` with 200 status
- `IntegrityError` from concurrent submissions is caught and handled gracefully

### Replayability

- All events are stored immutably in the `Event` table
- State can be reconstructed at any point by replaying events through the reducer
- `up_to` parameter allows partial replay to any timestamp

### Auditability

- Every resolution creates an `AuditLog` entry
- Audit includes: events considered, rule applied, explanation, previous/final state
- Audit trail is immutable and ordered by decision timestamp

### Performance

- Processing time measured with `time.perf_counter()` and returned in response
- Typical processing time: 15-35ms per event (well under 500ms target)
- No external API calls or ML/LLM services in the processing path

### Concurrency Assumption

- Single-process, synchronous execution
- No distributed locks or coordination
- `IntegrityError` handling covers race conditions on duplicate `event_id`
- Not designed for concurrent writes to the same order from multiple processes

---

## 17. Environment Configuration

### Backend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | SQLite (`db.sqlite3`) | PostgreSQL connection string |
| `SECRET_KEY` | Yes (production) | `dev-insecure-key-change-in-production` | Django secret key |
| `DEBUG` | No | `False` | Django debug mode (set `DEBUG=true` for local dev) |
| `ALLOWED_HOSTS` | No | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `CORS_ALLOWED_ORIGINS` | No | `http://localhost:5173` | Comma-separated allowed CORS origins |

### Frontend

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `VITE_API_BASE` | No | `http://localhost:8000/api` | Backend API base URL (set for deployed environments) |

### `.env.example` (backend)

``````
# Copy to .env and set real values for production.

# Django
SECRET_KEY=change-me-to-a-long-random-string
DEBUG=false
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173

# Database
DATABASE_URL=postgres://user:password@localhost:5432/vgrand

# Supabase (optional)
# SUPABASE_URL=https://your-project.supabase.co
# SUPABASE_ANON_KEY=your-anon-public-key
# SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
``````

### `.env.example` (frontend)

```
VITE_API_BASE=http://localhost:8000/api
```

### Dependencies

**Backend** (`requirements.txt`):
```
Django==5.0.6
djangorestframework==3.15.1
django-cors-headers==4.3.1
psycopg2-binary==2.9.9
dj-database-url==2.2.0
gunicorn==22.0.0
whitenoise==6.7.0
```

**Deployment**: `Procfile` runs `gunicorn vgrand.wsgi` for web and `python manage.py migrate --noinput && python manage.py collectstatic --noinput` for release. WhiteNoise serves static files.

**Frontend** (`package.json`):
```
react: ^18.3.1
react-dom: ^18.3.1
@vitejs/plugin-react: ^4.3.1
tailwindcss: ^3.4.6
vite: ^5.3.4
```

No external UI libraries (no axios, no lucide-react, no Material UI, no Bootstrap).

---

## 18. Project Structure

```
Hackton/
├── .gitignore
├── README.md
├── document.md                    ← this file
├── docs/
│   └── postman_collection.json    ← Postman API collection
├── backend/
│   ├── .env.example
│   ├── Procfile                   ← Railway deploy (gunicorn + migrate/collectstatic)
│   ├── manage.py
│   ├── requirements.txt
│   ├── db.sqlite3                 ← auto-generated (gitignored)
│   ├── vgrand/                    ← Django project
│   │   ├── __init__.py
│   │   ├── settings.py            ← SOURCE_PRIORITY, VALID_TRANSITIONS, DB config
│   │   ├── urls.py                ← root URL conf (admin + api/)
│   │   ├── asgi.py
│   │   └── wsgi.py
│   ├── orders/                    ← Main application
│   │   ├── __init__.py
│   │   ├── admin.py
│   │   ├── apps.py
│   │   ├── models.py              ← Event, OrderState, AuditLog, Location, MenuItem, ...
│   │   ├── serializers.py         ← DRF serializers
│   │   ├── tests.py               ← 30 tests
│   │   ├── urls.py                ← API URL routes
│   │   ├── views.py               ← API views (submit_event, list_orders, stats, ...)
│   │   ├── migrations/
│   │   │   ├── 0001_initial.py
│   │   │   └── 0002_event_location_id.py
│   │   ├── management/
│   │   │   └── commands/
│   │   │       └── load_fixture.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── ingestion.py       ← validate_event, check_duplicate, save_event
│   │       ├── conflict_resolver.py ← reducer, resolve_event, generate_explanation
│   │       ├── state_manager.py   ← get_current_state, list_all_orders, get_history
│   │       ├── replay_engine.py   ← replay_order
│   │       ├── audit_generator.py ← create_audit_entry, get_audit_trail
│   │       ├── inventory_manager.py ← check_inventory, reserve_inventory, release_inventory
│   │       ├── anomaly_detector.py ← detect_anomalies
│   │       └── driver_notifier.py ← notify_driver
│   └── fixtures/
│       ├── 01_duplicate_events.json
│       ├── 02_late_out_of_order.json
│       ├── 03_conflicting_reservations.json
│       ├── 04_conflicting_statuses.json
│       ├── 05_partial_updates.json
│       ├── 06_out_of_order_transitions.json
│       └── 07_anomaly_pattern.json
└── frontend/
    ├── .env.example               ← VITE_API_BASE for deployed environments
    ├── package.json
    ├── package-lock.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx                ← Sidebar + tab navigation
        ├── index.css              ← Tailwind + badge classes
        ├── api/
        │   └── client.js          ← fetch() wrapper with error handling
        └── components/
            ├── Dashboard.jsx
            ├── EventSubmitter.jsx
            ├── OrderDetail.jsx
            ├── AuditTrail.jsx
            ├── ReplayTimeline.jsx
            ├── InventoryView.jsx
            └── AnomalyAlerts.jsx
```

---

## Demo Script

### Step 1: Setup

```bash
# Terminal 1 — Backend
cd backend
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

### Step 2: Load Fixtures

```bash
cd backend
python manage.py load_fixture fixtures/01_duplicate_events.json --seed-inventory
python manage.py load_fixture fixtures/02_late_out_of_order.json
python manage.py load_fixture fixtures/03_conflicting_reservations.json
python manage.py load_fixture fixtures/04_conflicting_statuses.json
python manage.py load_fixture fixtures/05_partial_updates.json
python manage.py load_fixture fixtures/06_out_of_order_transitions.json
python manage.py load_fixture fixtures/07_anomaly_pattern.json
```

### Step 3: Verify via Dashboard

1. Open `http://localhost:5173` — Dashboard shows all orders with stats
2. Click any order → Order Detail tab shows current state + version history
3. Audit Trail tab → expand entries to see explanations and state diffs
4. Replay tab → see step-by-step timeline reconstruction
5. Inventory tab → see stock levels for Downtown location
6. Anomalies tab → see detected anomaly patterns
7. Submit Event tab → manually submit events or load fixtures via quick buttons

### Step 4: Verify via API

```bash
# Health check
curl http://localhost:8000/api/health

# List orders
curl http://localhost:8000/api/orders

# Get audit trail
curl http://localhost:8000/api/orders/ORD-005/audit

# Replay with timestamp filter
curl "http://localhost:8000/api/orders/ORD-002/replay?up_to=2026-08-15T10:05:00Z"

# Get stats
curl http://localhost:8000/api/stats

# Submit a new event
curl -X POST http://localhost:8000/api/events \
  -H "Content-Type: application/json" \
  -d '{"event_id": "demo-1", "source": "pos", "order_id": "ORD-DEMO", "timestamp": "2026-08-15T10:00:00Z", "items": [{"name": "Burger", "quantity": 1}], "status": "pending"}'
```

### Step 5: Run Tests

```bash
cd backend
python manage.py test --verbosity=2
```
